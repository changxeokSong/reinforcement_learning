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
    public class Room : MonoBehaviour
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
        public const int MaxLasers = 6;

        public static int DefaultLevel = 3;         // Python 없이 실행할 때의 레벨 (0~4 키로 바꾼다)

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
        Transform vaultDoor;
        float doorOpen;
        public float lastResultTime = -10f;

        System.Random rng;
        Materials mats;
        LaserAgent agent;

        // ---- 화면 ----
        Transform agentVis, agentYaw, agentBody;
        bool hasModel;
        Transform wingL, wingR, legL, legR;
        float yaw, walkPhase;
        readonly List<Transform> laserGlow = new List<Transform>();
        readonly List<Transform> laserVis = new List<Transform>();
        readonly List<Renderer> laserRend = new List<Renderer>();
        readonly List<Transform[]> laserCaps = new List<Transform[]>();
        Vector3 prevPos;
        bool prevCrouch;
        float prevTime;

        [System.Serializable]
        public class Materials
        {
            public Material floor, wall, agent, visor, laser, laserOff, vault, start, goal, emitter, glow, strip, particle;
            public GameObject character;     // 알바트로스 3D 모델 (없으면 도형으로 만든 캐릭터)
        }

        public static Room Create(int index, Vector3 origin, Materials mats, int seed)
        {
            var go = new GameObject($"Room{index}");
            go.transform.position = origin;
            var room = go.AddComponent<Room>();
            room.index = index;
            room.mats = mats;
            room.rng = new System.Random(seed * 1000 + index);
            room.BuildVisuals();
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

        public void ResetEpisode()
        {
            var p = Academy.Instance.EnvironmentParameters;
            int lv = Mathf.RoundToInt(p.GetWithDefault("level", DefaultLevel));
            level = lv < 0 ? 1 + rng.Next(4) : Mathf.Clamp(lv, 0, 4);
            obsMode = Mathf.RoundToInt(p.GetWithDefault("obs_mode", 1f));
            time = 0f;
            pos = new Vector3(Rand(-2.5f, 2.5f), 0f, StartZ);
            vel = Vector3.zero;
            grounded = true;
            crouch = false;
            slideTimer = 0f;
            GenerateLasers(level);
            prevPos = pos;
            prevCrouch = crouch;
            prevTime = time;
        }

        float Rand(float a, float b) => a + (float)rng.NextDouble() * (b - a);
        float Sign() => rng.Next(2) == 0 ? -1f : 1f;

        // ------------------------------------------------------------------
        // 레벨: 레이저 배치
        // ------------------------------------------------------------------
        void GenerateLasers(int lv)
        {
            lasers.Clear();
            switch (lv)
            {
                case 0:
                    break;
                case 1:
                    lasers.Add(MakeBar(-3f + Rand(-1f, 1f), moving: false));
                    lasers.Add(MakeBar(3f + Rand(-1f, 1f), moving: false));
                    break;
                case 2:
                    lasers.Add(MakeBar(-4f + Rand(-0.5f, 0.5f), moving: false));
                    lasers.Add(MakeSweeper(0.5f + Rand(-0.5f, 0.5f), 1f));
                    lasers.Add(MakeBar(5f + Rand(-0.5f, 0.5f), moving: true));
                    break;
                case 3:
                {
                    var kinds = new List<LaserKind> { LaserKind.Bar, LaserKind.Sweeper, LaserKind.Rotor, LaserKind.Blinker };
                    Shuffle(kinds);
                    float[] slots = { -5f, -1.5f, 2f, 5.5f };
                    for (int i = 0; i < 4; i++) lasers.Add(Make(kinds[i], slots[i] + Rand(-0.3f, 0.3f), 1f));
                    break;
                }
                default:
                {
                    float[] slots = { -5.5f, -3f, -0.5f, 2f, 4.5f };
                    foreach (var z in slots)
                        lasers.Add(Make((LaserKind)rng.Next(4), z + Rand(-0.2f, 0.2f), 1.3f));
                    break;
                }
            }
        }

        void Shuffle<T>(List<T> list)
        {
            for (int i = list.Count - 1; i > 0; i--)
            {
                int j = rng.Next(i + 1);
                (list[i], list[j]) = (list[j], list[i]);
            }
        }

        Laser Make(LaserKind kind, float z, float speed)
        {
            switch (kind)
            {
                case LaserKind.Bar: return MakeBar(z, moving: true, speed);
                case LaserKind.Sweeper: return MakeSweeper(z, speed);
                case LaserKind.Rotor:
                    return new Laser { kind = LaserKind.Rotor, z0 = z, height = rng.Next(2) == 0 ? 0.35f : 1.35f,
                        omega = Sign() * Rand(0.8f, 1.4f) * speed, phase = Rand(0f, 6.283f) };
                default:
                    return new Laser { kind = LaserKind.Blinker, z0 = z, height = 0.75f,
                        period = Rand(1.5f, 2.5f) / speed, duty = 0.5f, phase = Rand(0f, 1f) };
            }
        }

        Laser MakeBar(float z, bool moving, float speed = 1f) => new Laser
        {
            kind = LaserKind.Bar, z0 = z, height = rng.Next(2) == 0 ? 0.35f : 1.35f,
            amp = moving ? 1f : 0f, omega = Rand(1f, 2f) * speed, phase = Rand(0f, 6.283f),
        };

        Laser MakeSweeper(float z, float speed) => new Laser
        {
            kind = LaserKind.Sweeper, z0 = z, omega = Rand(1.2f, 2f) * speed, phase = Rand(0f, 6.283f),
        };

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
            int mx = action % 3 - 1;
            int mz = (action / 3) % 3 - 1;
            int v = action / 9;              // 0 없음, 1 점프, 2 숙이기
            float z0 = pos.z;
            progress = 0f;
            for (int s = 0; s < SubSteps; s++)
            {
                // 숙이기는 슬라이딩: 한 번 누르면 SlideTime 동안 몸을 낮춘 채 미끄러진다
                if (v == 2 && grounded && slideTimer <= 0f) { slideTimer = SlideTime; slides++; }
                crouch = slideTimer > 0f;
                if (crouch) slideTimer -= SubDt;
                if (v == 1 && grounded && !crouch)
                {
                    vel.y = JumpSpeed;
                    grounded = false;
                    jumps++;
                }
                var dir = new Vector2(mx, mz);
                if (dir.sqrMagnitude > 0f) dir.Normalize();
                float speed = RunSpeed;
                vel.x = dir.x * speed;
                vel.z = dir.y * speed;
                if (!grounded)
                {
                    vel.y -= Gravity * SubDt;
                    pos.y += vel.y * SubDt;
                    if (pos.y <= 0f)
                    {
                        pos.y = 0f;
                        vel.y = 0f;
                        grounded = true;
                    }
                }
                pos.x = Mathf.Clamp(pos.x + vel.x * SubDt, -HalfWidth + AgentRadius, HalfWidth - AgentRadius);
                pos.z = Mathf.Clamp(pos.z + vel.z * SubDt, -HalfLength + AgentRadius, HalfLength - AgentRadius);
                time += SubDt;

                if (HitsLaser())
                {
                    progress = (pos.z - z0) / (GoalZ - StartZ);
                    return Finish(Outcome.Hit);
                }
                if (pos.z >= GoalZ)
                {
                    progress = (pos.z - z0) / (GoalZ - StartZ);
                    return Finish(Outcome.Goal);
                }
            }
            progress = (pos.z - z0) / (GoalZ - StartZ);
            return time >= TimeLimit ? Finish(Outcome.Timeout) : Outcome.None;
        }

        Outcome Finish(Outcome o)
        {
            if (o == Outcome.Goal) { successes++; lastResult = "SUCCESS"; }
            else if (o == Outcome.Hit) { hits++; lastResult = "LASER HIT"; }
            else { timeouts++; lastResult = "TIME OUT"; }
            lastResultTime = Time.time;
            return o;
        }

        /// <summary>화면에 그려지는 에이전트 위치 (효과 연출용).</summary>
        public Vector3 AgentWorldPos => agentVis != null ? agentVis.position : transform.TransformPoint(pos);

        /// <summary>에이전트에서 가장 가까운 켜진 레이저까지의 거리 (레이저 소리 크기용).</summary>
        public float NearestLaserDistance()
        {
            AgentSegment(out var a, out var b);
            float best = 99f;
            foreach (var l in lasers)
            {
                if (!l.Active(time)) continue;
                l.Segment(time, out var p, out var q);
                best = Mathf.Min(best, Laser.SegmentDistance(a, b, p, q));
            }
            return best;
        }

        void AgentSegment(out Vector3 a, out Vector3 b)
        {
            float h = crouch ? CrouchHeight : StandHeight;
            a = new Vector3(pos.x, pos.y + AgentRadius, pos.z);
            b = new Vector3(pos.x, pos.y + h - AgentRadius, pos.z);
        }

        bool HitsLaser()
        {
            AgentSegment(out var a, out var b);
            foreach (var l in lasers)
            {
                if (!l.Active(time)) continue;
                l.Segment(time, out var p, out var q);
                if (Laser.SegmentDistance(a, b, p, q) < AgentRadius + Laser.Radius) return true;
            }
            return false;
        }

        // ------------------------------------------------------------------
        // 관측 (66개)
        // ------------------------------------------------------------------
        public void Observe(List<float> o)
        {
            o.Add(pos.x / HalfWidth);
            o.Add(pos.z / HalfLength);
            o.Add(pos.y);
            o.Add(vel.x / RunSpeed);
            o.Add(vel.z / RunSpeed);
            o.Add(vel.y / JumpSpeed);
            o.Add(Mathf.Max(slideTimer, 0f) / SlideTime);     // 슬라이딩 남은 비율 (0이면 서 있음)
            o.Add(grounded ? 1f : 0f);
            o.Add(time / TimeLimit);
            o.Add(level / 4f);
            o.Add((GoalZ - pos.z) / (2f * HalfLength));

            if (obsMode == 0) { ObserveRaw(o); return; }

            // 레이저 5개: 앞에 있는 것부터(지나간 것은 뒤로) 정렬한다.
            // 레이저마다 종류(4), 에이전트에 가장 가까운 지점의 상대 x·실제 높이·상대 z,
            // 그 지점의 속도(x, z), 켜짐, 깜빡임 전환까지 남은 시간 → 11개
            var center = new Vector3(pos.x, pos.y + 0.9f, pos.z);
            var items = new List<(float key, int i, Vector3 c)>();
            for (int i = 0; i < lasers.Count; i++)
            {
                lasers[i].Segment(time, out var p, out var q);
                var c = ClosestPoint(center, p, q);
                float dz = c.z - pos.z;
                // 앞(또는 거의 겹친) 레이저는 거리 순, 이미 지나간 레이저는 그 뒤
                float key = dz > -0.6f ? Mathf.Abs(dz) : 100f - dz;
                items.Add((key, i, c));
            }
            items.Sort((x, y) => x.key.CompareTo(y.key));
            for (int k = 0; k < NearestLasers; k++)
            {
                if (k >= items.Count)
                {
                    for (int j = 0; j < 11; j++) o.Add(0f);
                    continue;
                }
                var l = lasers[items[k].i];
                var c = items[k].c;
                for (int kind = 0; kind < 4; kind++) o.Add((int)l.kind == kind ? 1f : 0f);
                o.Add((c.x - pos.x) / HalfWidth);
                o.Add(c.y / 1.5f);
                o.Add((c.z - pos.z) / 5f);
                l.Segment(time + 0.1f, out var p2, out var q2);
                var c2 = ClosestPoint(center, p2, q2);
                o.Add((c2.x - c.x) / 0.1f / RunSpeed);
                o.Add((c2.z - c.z) / 0.1f / RunSpeed);
                o.Add(l.Active(time) ? 1f : 0f);
                o.Add(l.TimeToToggle(time) / 2f);   // 깜빡이: 다음 전환까지 남은 시간 (종류 표시가 있으므로 '존재' 대신)
            }
        }

        /// <summary>처음 설계한 관측: 가까운 순서로 레이저 선분의 양 끝점(상대 좌표), 중심 속도, 켜짐, 존재.</summary>
        void ObserveRaw(List<float> o)
        {
            var center = new Vector3(pos.x, pos.y + 0.9f, pos.z);
            var order = new List<(float d, int i)>();
            for (int i = 0; i < lasers.Count; i++)
            {
                lasers[i].Segment(time, out var p, out var q);
                order.Add((Laser.SegmentDistance(center, center, p, q), i));
            }
            order.Sort((x, y) => x.d.CompareTo(y.d));
            const float scale = 5f;
            for (int k = 0; k < NearestLasers; k++)
            {
                if (k >= order.Count)
                {
                    for (int j = 0; j < 11; j++) o.Add(0f);
                    continue;
                }
                var l = lasers[order[k].i];
                l.Segment(time, out var p, out var q);
                l.Segment(time + 0.05f, out var p2, out var q2);
                l.Segment(time - 0.05f, out var p0, out var q0);
                var vMid = ((p2 + q2) - (p0 + q0)) * 0.5f / 0.1f;
                Vector3 ra = (p - center) / scale, rb = (q - center) / scale;
                o.Add(ra.x); o.Add(ra.y); o.Add(ra.z);
                o.Add(rb.x); o.Add(rb.y); o.Add(rb.z);
                o.Add(vMid.x / scale); o.Add(vMid.y / scale); o.Add(vMid.z / scale);
                o.Add(l.Active(time) ? 1f : 0f);
                o.Add(1f);
            }
        }

        static Vector3 ClosestPoint(Vector3 x, Vector3 a, Vector3 b)
        {
            var d = b - a;
            float t = Mathf.Clamp01(Vector3.Dot(x - a, d) / Mathf.Max(d.sqrMagnitude, 1e-8f));
            return a + d * t;
        }

        // ------------------------------------------------------------------
        // 화면
        // ------------------------------------------------------------------
        Transform Prim(PrimitiveType type, string name, Transform parent, Vector3 localPos, Vector3 scale, Material m)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            Destroy(go.GetComponent<Collider>());
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = scale;
            var r = go.GetComponent<Renderer>();
            r.sharedMaterial = m;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            return go.transform;
        }

        void BuildVisuals()
        {
            var t = transform;
            float W = HalfWidth * 2f, L = HalfLength * 2f;
            Prim(PrimitiveType.Cube, "Floor", t, new Vector3(0, -0.05f, 0), new Vector3(W, 0.1f, L), mats.floor);
            for (int i = -4; i <= 4; i++)   // 바닥 줄무늬
                Prim(PrimitiveType.Cube, "Stripe", t, new Vector3(0, 0.002f, i * 2f), new Vector3(W, 0.004f, 0.04f), mats.wall);
            Prim(PrimitiveType.Cube, "WallL", t, new Vector3(-HalfWidth - 0.1f, 1.0f, 0), new Vector3(0.2f, 2f, L), mats.wall);
            Prim(PrimitiveType.Cube, "WallR", t, new Vector3(HalfWidth + 0.1f, 1.0f, 0), new Vector3(0.2f, 2f, L), mats.wall);
            Prim(PrimitiveType.Cube, "WallBack", t, new Vector3(0, 0.3f, -HalfLength - 0.1f), new Vector3(W + 0.4f, 0.6f, 0.2f), mats.wall);
            Prim(PrimitiveType.Cube, "WallFront", t, new Vector3(0, 1.0f, HalfLength + 0.1f), new Vector3(W + 0.4f, 2f, 0.2f), mats.wall);
            Prim(PrimitiveType.Cube, "StartPad", t, new Vector3(0, 0.005f, StartZ), new Vector3(W, 0.01f, 1.4f), mats.start);
            Prim(PrimitiveType.Cube, "GoalLine", t, new Vector3(0, 0.006f, GoalZ), new Vector3(W, 0.012f, 0.12f), mats.goal);
            // 금고: 어두운 안쪽, 금괴, 경첩으로 열리는 문
            Prim(PrimitiveType.Cube, "VaultBody", t, new Vector3(0, 0.75f, 9.5f), new Vector3(1.9f, 1.5f, 0.8f), mats.emitter);
            for (int i = 0; i < 3; i++)
                Prim(PrimitiveType.Cube, "GoldBar", t, new Vector3(-0.45f + i * 0.45f, 0.2f + (i % 2) * 0.16f, 9.3f),
                     new Vector3(0.38f, 0.14f, 0.22f), mats.vault);
            vaultDoor = new GameObject("VaultHinge").transform;
            vaultDoor.SetParent(t, false);
            vaultDoor.localPosition = new Vector3(-0.85f, 0.75f, 9.08f);
            var door = Prim(PrimitiveType.Cube, "VaultDoor", vaultDoor, new Vector3(0.85f, 0, 0), new Vector3(1.7f, 1.4f, 0.12f), mats.vault);
            Prim(PrimitiveType.Cylinder, "VaultDial", door, new Vector3(0, 0.05f, -0.6f), new Vector3(0.22f, 0.3f, 0.22f), mats.emitter)
                .localRotation = Quaternion.Euler(90, 0, 0);

            // 벽의 조명 띠
            foreach (float sx in new[] { -1f, 1f })
                Prim(PrimitiveType.Cube, "Strip", t, new Vector3(sx * (HalfWidth + 0.0f), 1.6f, 0), new Vector3(0.03f, 0.04f, L), mats.strip);

            // 에이전트: 위치(agentVis) → 방향(agentYaw) → 자세(agentBody, 크기·기울기) → 모델
            agentVis = new GameObject("AgentVis").transform;
            agentVis.SetParent(t, false);
            agentYaw = new GameObject("Yaw").transform;
            agentYaw.SetParent(agentVis, false);
            agentBody = new GameObject("Pose").transform;
            agentBody.SetParent(agentYaw, false);
            hasModel = mats.character != null;
            if (hasModel)
            {
                var model = Instantiate(mats.character, agentBody);
                wingL = model.transform.Find("WingL");
                wingR = model.transform.Find("WingR");
                legL = model.transform.Find("LegL");
                legR = model.transform.Find("LegR");
                foreach (var c in model.GetComponentsInChildren<Collider>()) Destroy(c);
                // 모델 크기를 키 1.7m로 맞추고 발이 바닥(0)에 닿게 놓는다
                var rends = model.GetComponentsInChildren<Renderer>();
                var b = rends[0].bounds;
                foreach (var r in rends) b.Encapsulate(r.bounds);
                float s = 1.7f / b.size.y;
                model.transform.localScale *= s;
                model.transform.localPosition = new Vector3(-(b.center.x - t.position.x) * s, -(b.min.y) * s, 0f);
            }
            else
            {
                Prim(PrimitiveType.Capsule, "Body", agentBody, new Vector3(0, 0.9f, 0), new Vector3(0.6f, 0.9f, 0.6f), mats.agent);
                Prim(PrimitiveType.Cube, "Visor", agentBody, new Vector3(0, 1.35f, 0.25f), new Vector3(0.5f, 0.14f, 0.2f), mats.visor);
            }

            for (int i = 0; i < MaxLasers; i++)
            {
                var beam = Prim(PrimitiveType.Cylinder, "Laser", t, Vector3.zero, Vector3.one, mats.laser);
                laserGlow.Add(Prim(PrimitiveType.Cylinder, "Glow", beam, Vector3.zero, new Vector3(3.5f, 1f, 3.5f), mats.glow));
                var caps = new[]
                {
                    Prim(PrimitiveType.Cube, "Emitter", t, Vector3.zero, Vector3.one * 0.18f, mats.emitter),
                    Prim(PrimitiveType.Cube, "Emitter", t, Vector3.zero, Vector3.one * 0.18f, mats.emitter),
                };
                laserVis.Add(beam);
                laserRend.Add(beam.GetComponent<Renderer>());
                laserCaps.Add(caps);
            }
        }

        void Update()
        {
            if (Application.isBatchMode || agentVis == null) return;
            // 시뮬레이션은 0.1초 단위라서 화면은 직전 상태와 현재 상태 사이를 보간해서 그린다
            float alpha = Mathf.Clamp01((Time.time - Time.fixedTime) / Time.fixedDeltaTime);
            var p = Vector3.Lerp(prevPos, pos, alpha);
            agentVis.localPosition = p;
            AnimateAgent(alpha < 0.5f ? prevCrouch : crouch);

            bool opening = lastResult == "SUCCESS" && Time.time - lastResultTime < 1.6f;
            doorOpen = Mathf.MoveTowards(doorOpen, opening ? 1f : 0f, Time.deltaTime * (opening ? 3f : 1.5f));
            vaultDoor.localRotation = Quaternion.Euler(0, -105f * Mathf.SmoothStep(0, 1, doorOpen), 0);

            float t = Mathf.Lerp(prevTime, time, alpha);
            for (int i = 0; i < MaxLasers; i++)
            {
                bool show = i < lasers.Count;
                laserVis[i].gameObject.SetActive(show);
                laserCaps[i][0].gameObject.SetActive(show);
                laserCaps[i][1].gameObject.SetActive(show);
                if (!show) continue;
                var l = lasers[i];
                l.Segment(t, out var a, out var b);
                var mid = (a + b) / 2f;
                var dir = b - a;
                laserVis[i].localPosition = mid;
                laserVis[i].localRotation = Quaternion.FromToRotation(Vector3.up, dir.normalized);
                bool on = l.Active(t);
                float thick = on ? 0.08f : 0.03f;
                laserVis[i].localScale = new Vector3(thick, dir.magnitude / 2f, thick);
                laserGlow[i].gameObject.SetActive(on);
                laserRend[i].sharedMaterial = on ? mats.laser : mats.laserOff;
                laserCaps[i][0].localPosition = a;
                laserCaps[i][1].localPosition = b;
            }
        }
    
        /// <summary>뒤뚱 걷기, 점프할 때 늘어나기, 숙일 때 납작해지기, 이동 방향 보기.</summary>
        void AnimateAgent(bool c)
        {
            float dt = Time.deltaTime;
            var flat = new Vector2(vel.x, vel.z);
            float speed = flat.magnitude;
            if (speed > 0.1f) yaw = Mathf.MoveTowardsAngle(yaw, Mathf.Atan2(vel.x, vel.z) * Mathf.Rad2Deg, 720f * dt);
            agentYaw.localRotation = Quaternion.Euler(0, yaw, 0);

            Vector3 scale = Vector3.one;
            float roll = 0f, pitch = 0f, bob = 0f;
            if (grounded && speed > 0.1f)
            {
                walkPhase += dt * speed * 3.2f;
                roll = Mathf.Sin(walkPhase) * 9f;
                bob = Mathf.Abs(Mathf.Sin(walkPhase)) * 0.06f;
                pitch = 6f;
            }
            if (!grounded)
            {
                float stretch = Mathf.Clamp(vel.y / JumpSpeed, -1f, 1f) * 0.12f;
                scale = new Vector3(1f - stretch * 0.5f, 1f + stretch, 1f - stretch * 0.5f);
                pitch = -8f * Mathf.Sign(vel.y);
            }
            if (c)
            {
                scale = new Vector3(1.2f, CrouchHeight / StandHeight, 1.2f);
                pitch = 18f;
            }
            if (Time.time - lastResultTime < 0.6f && lastResult == "LASER HIT")
            {
                roll += Mathf.Sin(Time.time * 50f) * 20f;
                scale *= 1f + 0.08f * Mathf.Sin(Time.time * 40f);
            }
            else if (Time.time - lastResultTime < 0.6f && lastResult == "SUCCESS")
            {
                bob += Mathf.Abs(Mathf.Sin(Time.time * 14f)) * 0.3f;
            }
            AnimateLimbs(c);
            agentBody.localPosition = new Vector3(0, bob, 0);
            agentBody.localRotation = Quaternion.Euler(pitch, 0, roll);
            agentBody.localScale = Vector3.Lerp(agentBody.localScale, scale, 1f - Mathf.Exp(-20f * dt));
        }
    
        /// <summary>날개: 서 있을 때 살짝 내림, 점프할 때 퍼덕임, 숙일 때 접기. 다리: 걸을 때 번갈아 앞뒤로.</summary>
        void AnimateLimbs(bool c)
        {
            if (wingL == null) return;
            float t = Time.time;
            float speed = new Vector2(vel.x, vel.z).magnitude;
            float raise = -28f + (speed > 0.1f ? Mathf.Sin(walkPhase * 2f) * 8f : Mathf.Sin(t * 2f) * 3f);
            if (!grounded) raise = 10f + Mathf.Sin(t * 22f) * 45f;
            if (c) raise = -62f;
            bool recent = Time.time - lastResultTime < 0.8f;
            if (recent && lastResult == "LASER HIT") raise = Mathf.Sin(t * 40f) * 60f;
            if (recent && lastResult == "SUCCESS") raise = 55f + Mathf.Sin(t * 16f) * 25f;
            foreach (var w in new[] { wingL, wingR })
            {
                float side = Mathf.Sign(w.localPosition.x);
                w.localRotation = Quaternion.Slerp(w.localRotation, Quaternion.Euler(0, 0, side * raise), 1f - Mathf.Exp(-18f * Time.deltaTime));
            }
            float swing = grounded && speed > 0.1f ? Mathf.Sin(walkPhase) * 30f : 0f;
            if (!grounded) swing = 0f;
            float tuck = !grounded ? -25f : 0f;
            legL.localRotation = Quaternion.Euler(swing + tuck, 0, 0);
            legR.localRotation = Quaternion.Euler(-swing + tuck, 0, 0);
        }
    }
}
