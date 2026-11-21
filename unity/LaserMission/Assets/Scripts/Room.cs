using System.Collections.Generic;
using Unity.MLAgents;
using Unity.MLAgents.Policies;
using UnityEngine;

namespace LaserMission
{
    /// <summary>
    /// 레이저 방 하나. 게임 규칙(이동, 점프, 숙이기, 레이저 충돌, 금고 도착)과 화면을 맡는다.
    ///
    /// 물리 엔진(Rigidbody, Collider)은 쓰지 않는다. 위치를 직접 계산하고, 충돌은
    /// "에이전트 캡슐과 레이저 선분 사이의 거리"로 판정한다. 그래서 결과가 결정적이고 빠르다.
    /// 방은 x(폭) -4~4, z(길이) -10~10. 에이전트는 z=-8.5에서 출발해서 z=8.6(금고 앞)에 닿으면 성공.
    /// </summary>
    public partial class Room : MonoBehaviour
    {
        // ---- 방 크기와 규칙 ----
        public const float HalfWidth = 4f;
        public const float HalfLength = 10f;
        public const float StartZ = -8.5f;
        public const float GoalZ = 8.6f;
        public const float TimeLimit = 20f;
        public const float SubDt = 0.02f;           // 시뮬레이션 간격
        public const int SubSteps = 5;              // 결정 한 번 = 0.1초
        public const float AgentRadius = 0.3f;
        public const float StandHeight = 1.8f;
        public const float CrouchHeight = 1.0f;
        public const float RunSpeed = 4f;
        public const float SlideTime = 0.6f;        // 숙이기(슬라이딩) 한 번의 지속 시간
        public const float JumpSpeed = 5.5f;
        public const float Gravity = 15f;
        public const int NearestLasers = 5;
        public const int ObsSize = 11 + NearestLasers * 11;
        public const int NumActions = 27;           // 좌우 3 × 앞뒤 3 × (없음/점프/숙이기) 3
        public const int MaxLasers = 12;
        public const int MaxLevel = 10;

        public static int DefaultLevel = 3;
        public static int DefaultLevel6Design;
        public CampaignProgress Campaign { get; set; }

        // ---- 상태 ----
        public int index;
        public int level;
        public int obsMode = 1;      // 1: 설계한 특징(종류·높이·앞쪽 정렬), 0: 원시 선분 좌표 (비교 실험용)
        public float time;
        public Vector3 pos;          // 발 위치
        public Vector3 vel;
        public bool grounded = true;
        public bool crouch;
        public float slideTimer;
        public readonly List<Laser> lasers = new List<Laser>();
        public int successes, hits, timeouts;
        public string lastResult = "";
        public int jumps, slides;    // 효과음·연출용 카운터 (화면 쪽에서 바뀌었는지 본다)
        public float lastResultTime = -10f;

        LaserAgent agent;

        public static Room Create(int index, Vector3 origin, Materials mats, int seed, CampaignProgress campaign = null)
        {
            var go = new GameObject($"Room{index}");
            go.transform.position = origin;
            var room = go.AddComponent<Room>();
            room.index = index;
            room.mats = mats;
            room.Campaign = campaign;
            room.rng = new System.Random(seed * 1000 + index);
            if (!Application.isBatchMode) room.BuildVisuals();
            room.CreateAgent();
            return room;
        }

        // ------------------------------------------------------------------
        // 에이전트 (ML-Agents)
        // ------------------------------------------------------------------
        void CreateAgent()
        {
            // 비활성 상태에서 설정을 마친 뒤 켠다. 켜지는 순간 ML-Agents가 설정을 읽는다.
            var go = new GameObject("Agent");
            go.SetActive(false);
            go.transform.SetParent(transform, false);
            var bp = go.AddComponent<BehaviorParameters>();
            bp.BehaviorName = "LaserMission";
            bp.BrainParameters.VectorObservationSize = ObsSize;
            bp.BrainParameters.NumStackedVectorObservations = 1;
            bp.BrainParameters.ActionSpec = Unity.MLAgents.Actuators.ActionSpec.MakeDiscrete(NumActions);
            agent = go.AddComponent<LaserAgent>();
            agent.room = this;
            agent.MaxStep = 0;
            var dr = go.AddComponent<DecisionRequester>();
            dr.DecisionPeriod = 1;
            dr.TakeActionsBetweenDecisions = false;
            go.SetActive(true);
        }

        // ------------------------------------------------------------------
        // 한 번의 결정(0.1초) 진행
        // ------------------------------------------------------------------
        public enum Outcome { None, Goal, Hit, Timeout }

        /// <summary>행동 하나를 0.1초 동안 실행한다. 진행 거리(보조 보상용)와 결과를 돌려준다.</summary>
        public Outcome Step(int action, out float progress)
        {
            prevPos = pos;
            prevCrouch = crouch;
            prevTime = time;
            var next = CaptureMotion();
            var outcome = Advance(ref next, action, out int jumped, out int slid);
            progress = (next.Position.z - pos.z) / (GoalZ - StartZ);
            (pos, vel, grounded, crouch, slideTimer, time) =
                (next.Position, next.Velocity, next.Grounded, next.Crouch, next.SlideTimer, next.Time);
            jumps += jumped;
            slides += slid;
            return outcome == Outcome.None ? outcome : Finish(outcome);
        }

        struct Motion
        {
            public Vector3 Position, Velocity;
            public bool Grounded, Crouch;
            public float SlideTimer, Time;
        }

        Motion CaptureMotion() => new Motion
        {
            Position = pos, Velocity = vel, Grounded = grounded,
            Crouch = crouch, SlideTimer = slideTimer, Time = time,
        };

        public void FindSafeActions(bool[] safe, int horizon)
        {
            var start = CaptureMotion();
            for (int action = 0; action < NumActions; action++)
                safe[action] = CanSurvive(start, action, horizon);
        }

        bool CanSurvive(Motion state, int action, int steps)
        {
            var outcome = Advance(ref state, action, out _, out _);
            return outcome == Outcome.Goal ||
                (outcome == Outcome.None && (steps == 1 || HasSafeContinuation(state, steps - 1)));
        }

        bool HasSafeContinuation(Motion start, int steps)
        {
            // Waiting is common between gates, so check it before the full action set.
            const int waitAction = 4;
            if (CanSurvive(start, waitAction, steps)) return true;
            for (int action = 0; action < NumActions; action++)
                if (action != waitAction && CanSurvive(start, action, steps)) return true;
            return false;
        }

        Outcome Advance(ref Motion motion, int action, out int jumped, out int slid)
        {
            int mx = action % 3 - 1;
            int mz = (action / 3) % 3 - 1;
            int v = action / 9;              // 0 없음, 1 점프, 2 숙이기
            jumped = 0;
            slid = 0;
            var dir = new Vector2(mx, mz);
            if (dir.sqrMagnitude > 0f) dir.Normalize();
            motion.Velocity.x = dir.x * RunSpeed;
            motion.Velocity.z = dir.y * RunSpeed;
            for (int s = 0; s < SubSteps; s++)
            {
                // 숙이기는 슬라이딩: 한 번 누르면 SlideTime 동안 몸을 낮춘 채 미끄러진다
                if (v == 2 && motion.Grounded && motion.SlideTimer <= 0f)
                {
                    motion.SlideTimer = SlideTime;
                    slid++;
                }
                motion.Crouch = motion.SlideTimer > 0f;
                if (motion.Crouch) motion.SlideTimer -= SubDt;
                if (v == 1 && motion.Grounded && !motion.Crouch)
                {
                    motion.Velocity.y = JumpSpeed;
                    motion.Grounded = false;
                    jumped++;
                }
                if (!motion.Grounded)
                {
                    motion.Velocity.y -= Gravity * SubDt;
                    motion.Position.y += motion.Velocity.y * SubDt;
                    if (motion.Position.y <= 0f)
                    {
                        motion.Position.y = 0f;
                        motion.Velocity.y = 0f;
                        motion.Grounded = true;
                    }
                }
                motion.Position.x = Mathf.Clamp(motion.Position.x + motion.Velocity.x * SubDt, -HalfWidth + AgentRadius, HalfWidth - AgentRadius);
                motion.Position.z = Mathf.Clamp(motion.Position.z + motion.Velocity.z * SubDt, -HalfLength + AgentRadius, HalfLength - AgentRadius);
                motion.Time += SubDt;

                if (HitsLaser(motion)) return Outcome.Hit;
                if (motion.Position.z >= GoalZ) return Outcome.Goal;
            }
            return motion.Time >= TimeLimit ? Outcome.Timeout : Outcome.None;
        }

        Outcome Finish(Outcome o)
        {
            if (o == Outcome.Goal) { successes++; lastResult = "SUCCESS"; }
            else if (o == Outcome.Hit) { hits++; lastResult = "LASER HIT"; }
            else { timeouts++; lastResult = "TIME OUT"; }
            lastResultTime = Time.time;
            return o;
        }

        /// <summary>에이전트에서 가장 가까운 켜진 레이저까지의 거리 (레이저 소리 크기용).</summary>
        public float NearestLaserDistance()
        {
            AgentSegment(pos, crouch, out var a, out var b);
            float best = 99f;
            foreach (var l in lasers)
            {
                if (!l.Active(time)) continue;
                l.Segment(time, out var p, out var q);
                best = Mathf.Min(best, Laser.SegmentDistance(a, b, p, q));
            }
            return best;
        }

        static void AgentSegment(Vector3 position, bool crouching, out Vector3 a, out Vector3 b)
        {
            float h = crouching ? CrouchHeight : StandHeight;
            a = new Vector3(position.x, position.y + AgentRadius, position.z);
            b = new Vector3(position.x, position.y + h - AgentRadius, position.z);
        }

        bool HitsLaser(Motion motion)
        {
            AgentSegment(motion.Position, motion.Crouch, out var a, out var b);
            foreach (var l in lasers)
            {
                if (!l.Active(motion.Time)) continue;
                l.Segment(motion.Time, out var p, out var q);
                if (l.IsWall)
                {
                    // 벽은 높이와 상관없이 막는다: 바닥 평면에서의 거리로 판정
                    var f = new Vector3(motion.Position.x, 0f, motion.Position.z);
                    p.y = 0f; q.y = 0f;
                    if (Laser.SegmentDistance(f, f, p, q) < AgentRadius + Laser.WallHalfThickness) return true;
                    continue;
                }
                if (Laser.SegmentDistance(a, b, p, q) < AgentRadius + Laser.Radius) return true;
            }
            return false;
        }
    }
}
