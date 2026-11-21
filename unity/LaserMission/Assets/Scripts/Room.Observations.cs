using System.Collections.Generic;
using UnityEngine;

namespace LaserMission
{
    public partial class Room
    {
        readonly List<(float key, int i, Vector3 c)> observationItems = new List<(float, int, Vector3)>(MaxLasers);
        readonly List<(float d, int i)> rawObservationOrder = new List<(float, int)>(MaxLasers);

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
            bool showCorridors = obsMode == 2 && level == 6;

            // 레이저 5개: 앞에 있는 것부터(지나간 것은 뒤로) 정렬한다.
            // 레이저마다 종류(4), 에이전트에 가장 가까운 지점의 상대 x·실제 높이·상대 z,
            // 그 지점의 속도(x, z), 켜짐, 깜빡임 전환까지 남은 시간 → 11개
            var center = new Vector3(pos.x, pos.y + 0.9f, pos.z);
            var items = observationItems;
            items.Clear();
            for (int i = 0; i < lasers.Count; i++)
            {
                var laser = lasers[i];
                if (showCorridors && laser.side > 0) continue;
                if (showCorridors && laser.side < 0)
                {
                    var gap = new Vector3(laser.GapX(time), Laser.WallHeight, laser.z0);
                    float gapDz = gap.z - pos.z;
                    items.Add((gapDz > -0.6f ? Mathf.Abs(gapDz) : 100f - gapDz, i, gap));
                    continue;
                }
                laser.Segment(time, out var p, out var q);
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
                bool corridor = showCorridors && l.side < 0;
                bool timedWall = showCorridors && l.fullWidthWall;
                for (int kind = 0; kind < 4; kind++)
                    o.Add((corridor ? kind < 2 : timedWall ? kind >= 2 : (int)l.kind == kind) ? 1f : 0f);
                o.Add((c.x - pos.x) / HalfWidth);
                o.Add(corridor ? (l.gapHalf - AgentRadius - Laser.WallHalfThickness) / HalfWidth : c.y / 1.5f);
                o.Add((c.z - pos.z) / 5f);
                Vector3 c2;
                if (corridor)
                    c2 = new Vector3(l.GapX(time + 0.1f), c.y, l.z0);
                else
                {
                    l.Segment(time + 0.1f, out var p2, out var q2);
                    c2 = ClosestPoint(center, p2, q2);
                }
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
            var order = rawObservationOrder;
            order.Clear();
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
    }
}
