using System.Collections.Generic;
using UnityEngine;

namespace LaserMission
{
    public partial class Room
    {
        static readonly float[] FenceHeights = { -0.7f, -0.35f, 0.45f, 0.9f };
        Materials mats;
        Transform vaultDoor;
        float doorOpen;
        // ---- 화면 ----
        Transform agentVis, agentYaw, agentBody;
        bool hasModel;
        Transform wingL, wingR, legL, legR;
        float yaw, walkPhase;
        readonly List<Transform> laserGlow = new List<Transform>();
        readonly List<Transform> laserVis = new List<Transform>();
        readonly List<Renderer> laserRend = new List<Renderer>();
        readonly List<Transform[]> laserCaps = new List<Transform[]>();
        readonly List<Transform[]> laserFence = new List<Transform[]>();
        Vector3 prevPos;
        bool prevCrouch;
        float prevTime;

        [System.Serializable]
        public class Materials
        {
            public Material floor, wall, agent, visor, laser, laserOff, vault, start, goal, emitter, glow, strip, particle;
            public GameObject character;     // 알바트로스 3D 모델 (없으면 도형으로 만든 캐릭터)
        }

        /// <summary>화면에 그려지는 에이전트 위치 (효과 연출용).</summary>
        public Vector3 AgentWorldPos => agentVis != null ? agentVis.position : transform.TransformPoint(pos);

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
                var fence = new Transform[4];
                for (int k = 0; k < 4; k++)
                    fence[k] = Prim(PrimitiveType.Cylinder, "Fence", t, Vector3.zero, Vector3.one, mats.laser);
                laserFence.Add(fence);
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
                if (!show)
                {
                    foreach (var beam in laserFence[i]) beam.gameObject.SetActive(false);
                    continue;
                }
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
                // 벽이면 위아래로 레이저를 여러 줄 더 그려서 울타리처럼 보이게 한다
                for (int k = 0; k < 4; k++)
                {
                    var fb = laserFence[i][k];
                    fb.gameObject.SetActive(l.IsWall && on);
                    if (!l.IsWall || !on) continue;
                    float dy = FenceHeights[k];
                    fb.localPosition = mid + Vector3.up * dy;
                    fb.localRotation = laserVis[i].localRotation;
                    fb.localScale = new Vector3(0.06f, dir.magnitude / 2f, 0.06f);
                }
                if (l.IsWall)
                {
                    laserCaps[i][0].localScale = laserCaps[i][1].localScale = new Vector3(0.18f, 2.0f, 0.18f);
                }
                else
                {
                    laserCaps[i][0].localScale = laserCaps[i][1].localScale = Vector3.one * 0.18f;
                }
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
