using UnityEngine;

namespace LaserMission
{
    public enum LaserKind { Bar, Sweeper, Rotor, Blinker }

    /// <summary>
    /// 레이저 하나의 움직임. 시간 t를 넣으면 그 순간의 선분(양 끝점)과 켜짐 여부를 계산한다.
    /// 물리 엔진을 쓰지 않고 식으로 계산하므로 같은 seed면 항상 같은 움직임이 나온다.
    /// </summary>
    public struct Laser
    {
        public LaserKind kind;
        public float z0;        // 기준 위치 (방 길이 방향)
        public float height;    // 높이 (Bar, Rotor, Blinker)
        public float amp;       // 앞뒤로 움직이는 폭 (Bar)
        public float omega;     // 각속도 (rad/s)
        public float phase;     // 시작 위상
        public float period;    // 깜빡임 주기 (Blinker)
        public float duty;      // 켜져 있는 비율 (Blinker)

        public const float Radius = 0.04f;
        public const float RotorHalfLength = 3.2f;
        public const float SweeperTop = 2.6f;

        public void Segment(float t, out Vector3 a, out Vector3 b)
        {
            float halfW = Room.HalfWidth;
            switch (kind)
            {
                case LaserKind.Bar:
                {
                    float z = z0 + amp * Mathf.Sin(omega * t + phase);
                    a = new Vector3(-halfW, height, z);
                    b = new Vector3(halfW, height, z);
                    break;
                }
                case LaserKind.Sweeper:
                {
                    float x = (halfW - 0.3f) * Mathf.Sin(omega * t + phase);
                    a = new Vector3(x, 0f, z0);
                    b = new Vector3(x, SweeperTop, z0);
                    break;
                }
                case LaserKind.Rotor:
                {
                    float th = omega * t + phase;
                    var d = new Vector3(Mathf.Cos(th), 0f, Mathf.Sin(th)) * RotorHalfLength;
                    var c = new Vector3(0f, height, z0);
                    a = c - d;
                    b = c + d;
                    break;
                }
                default: // Blinker
                    a = new Vector3(-halfW, height, z0);
                    b = new Vector3(halfW, height, z0);
                    break;
            }
        }

        public bool Active(float t)
        {
            if (kind != LaserKind.Blinker) return true;
            float f = t / period + phase;
            f -= Mathf.Floor(f);
            return f < duty;
        }

        /// <summary>두 선분 사이의 최소 거리 (캡슐-선분 충돌 판정에 쓴다).</summary>
        public static float SegmentDistance(Vector3 p1, Vector3 q1, Vector3 p2, Vector3 q2)
        {
            Vector3 d1 = q1 - p1, d2 = q2 - p2, r = p1 - p2;
            float a = Vector3.Dot(d1, d1), e = Vector3.Dot(d2, d2), f = Vector3.Dot(d2, r);
            float s, t;
            if (a <= 1e-8f && e <= 1e-8f) return (p1 - p2).magnitude;
            if (a <= 1e-8f) { s = 0f; t = Mathf.Clamp01(f / e); }
            else
            {
                float c = Vector3.Dot(d1, r);
                if (e <= 1e-8f) { t = 0f; s = Mathf.Clamp01(-c / a); }
                else
                {
                    float b = Vector3.Dot(d1, d2);
                    float denom = a * e - b * b;
                    s = denom > 1e-8f ? Mathf.Clamp01((b * f - c * e) / denom) : 0f;
                    t = (b * s + f) / e;
                    if (t < 0f) { t = 0f; s = Mathf.Clamp01(-c / a); }
                    else if (t > 1f) { t = 1f; s = Mathf.Clamp01((b - c) / a); }
                }
            }
            return ((p1 + d1 * s) - (p2 + d2 * t)).magnitude;
        }
    }
}
