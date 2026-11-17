using UnityEngine;

namespace LaserMission
{
    /// <summary>
    /// 0번 방(화면에 보이는 방)의 연출: 효과음, 불꽃·반짝이 파티클, 화면 흔들림.
    /// 효과음은 파일 없이 코드로 합성한다. 학습(화면 없음)에서는 아무것도 하지 않는다.
    /// </summary>
    public class Effects : MonoBehaviour
    {
        public Room room;
        public Transform cam;
        public Material particleMat;

        AudioSource sfx, hum;
        AudioClip zap, chime, jump, slide;
        ParticleSystem sparks, confetti;
        int lastJumps, lastSlides;
        float lastResultTime = -10f, shake;
        public bool muted;

        const int Rate = 44100;

        void Start()
        {
            if (Application.isBatchMode) { enabled = false; return; }
            foreach (var a in System.Environment.GetCommandLineArgs())
                if (a == "-mute") muted = true;
            sfx = gameObject.AddComponent<AudioSource>();
            hum = gameObject.AddComponent<AudioSource>();
            zap = Make("zap", 0.45f, (t, d) =>
                (Noise() * 0.6f + Saw(t, 900f - 1400f * t) * 0.5f) * Mathf.Exp(-t * 7f));
            chime = Make("chime", 1.1f, (t, d) =>
            {
                float[] notes = { 523.25f, 659.25f, 783.99f, 1046.5f };
                int k = Mathf.Min((int)(t / 0.12f), 3);
                float local = t - k * 0.12f;
                return Mathf.Sin(2 * Mathf.PI * notes[k] * t) * Mathf.Exp(-local * 3f) * 0.5f;
            });
            jump = Make("jump", 0.2f, (t, d) => Mathf.Sin(2 * Mathf.PI * (300f + 1800f * t) * t) * (1 - t / d) * 0.35f);
            slide = Make("slide", 0.35f, (t, d) => Noise() * Mathf.Sin(Mathf.PI * t / d) * 0.25f);
            hum.clip = Make("hum", 1f, (t, d) =>
                (Mathf.Sin(2 * Mathf.PI * 110f * t) + 0.5f * Mathf.Sin(2 * Mathf.PI * 220f * t)) * 0.3f);
            hum.loop = true;
            hum.volume = 0f;
            if (!muted) hum.Play();

            sparks = MakeParticles("Sparks", new Color(1f, 0.35f, 0.15f), 7f, 0.5f, 0.09f);
            confetti = MakeParticles("Confetti", new Color(1f, 0.85f, 0.3f), 5f, 1.4f, 0.12f);
            var main = confetti.main;
            main.gravityModifier = 0.6f;
        }

        static float Noise() => Random.value * 2f - 1f;
        static float Saw(float t, float f) => 2f * (t * f - Mathf.Floor(t * f + 0.5f));

        static AudioClip Make(string name, float seconds, System.Func<float, float, float> wave)
        {
            int n = (int)(seconds * Rate);
            var data = new float[n];
            for (int i = 0; i < n; i++) data[i] = Mathf.Clamp(wave(i / (float)Rate, seconds), -1f, 1f);
            var clip = AudioClip.Create(name, n, 1, Rate, false);
            clip.SetData(data, 0);
            return clip;
        }

        ParticleSystem MakeParticles(string name, Color color, float speed, float life, float size)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.playOnAwake = false;
            main.loop = false;
            main.startColor = new ParticleSystem.MinMaxGradient(color, Color.white);
            main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.4f, speed);
            main.startLifetime = new ParticleSystem.MinMaxCurve(life * 0.5f, life);
            main.startSize = new ParticleSystem.MinMaxCurve(size * 0.5f, size);
            main.gravityModifier = 1.2f;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.2f;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = particleMat;
            return ps;
        }

        void Play(AudioClip clip, float volume = 1f)
        {
            if (!muted && clip != null) sfx.PlayOneShot(clip, volume);
        }

        void Update()
        {
            if (room == null) return;
            if (Input.GetKeyDown(KeyCode.M))
            {
                muted = !muted;
                if (muted) hum.Stop(); else hum.Play();
            }
            if (room.jumps != lastJumps) { lastJumps = room.jumps; Play(jump, 0.6f); }
            if (room.slides != lastSlides) { lastSlides = room.slides; Play(slide, 0.8f); }
            if (room.lastResultTime != lastResultTime)
            {
                lastResultTime = room.lastResultTime;
                var p = room.AgentWorldPos + Vector3.up * 0.9f;
                if (room.lastResult == "LASER HIT")
                {
                    Play(zap, 0.9f);
                    sparks.transform.position = p;
                    sparks.Emit(70);
                    shake = 0.35f;
                }
                else if (room.lastResult == "SUCCESS")
                {
                    Play(chime, 0.8f);
                    confetti.transform.position = room.transform.position + new Vector3(0, 1.6f, 9f);
                    confetti.Emit(120);
                }
            }
            // 레이저에 가까울수록 웅웅거리는 소리가 커진다
            float d = room.NearestLaserDistance();
            hum.volume = Mathf.Lerp(hum.volume, Mathf.Clamp01(1.2f - d) * 0.35f, 0.2f);
        }

        void LateUpdate()
        {
            if (shake <= 0f || cam == null) return;
            cam.position += Random.insideUnitSphere * shake * 0.25f;
            shake = Mathf.Max(0f, shake - Time.deltaTime);
        }
    }
}
