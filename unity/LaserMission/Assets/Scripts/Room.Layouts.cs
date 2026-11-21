using System.Collections.Generic;
using Unity.MLAgents;
using UnityEngine;

namespace LaserMission
{
    public partial class Room
    {
        System.Random rng;
        readonly int[] lastCampaignLayouts = new int[MaxLevel + 1];

        public void ResetEpisode()
        {
            var p = Academy.Instance.EnvironmentParameters;
            var practiceRng = rng;
            int layout = -1;
            if (Campaign != null)
            {
                level = Campaign.Stage;
                layout = Campaign.LayoutSeed;
            }
            else
            {
                int lv = Mathf.RoundToInt(p.GetWithDefault("level", DefaultLevel));
                int maxLevel = Mathf.Clamp(Mathf.RoundToInt(p.GetWithDefault("max_level", 4f)), 1, MaxLevel);
                level = lv < 0 ? 1 + rng.Next(maxLevel) : Mathf.Clamp(lv, 0, MaxLevel);
                // level_mix 확률로 현재 레벨보다 낮은 레벨을 복습한다.
                if (level > 1 && rng.NextDouble() < p.GetWithDefault("level_mix", 0f)
                    && level >= p.GetWithDefault("level_mix_from", 2f))
                {
                    int reviewLevel = Mathf.RoundToInt(p.GetWithDefault("level_mix_target", 0f));
                    level = reviewLevel > 0 ? Mathf.Min(reviewLevel, level - 1) : 1 + rng.Next(level - 1);
                }
                if (level > 0 && p.GetWithDefault("campaign_layouts", 0f) > 0.5f)
                {
                    // 0은 이 방에서 아직 이 레벨을 플레이하지 않았음을 나타낸다.
                    // 학습 전용: training_layout(0~3)을 training_layout_prob 확률로 고정한다 (어려운 배치 집중 학습).
                    // 기본값(-1)이면 아래 무작위 선택과 난수 사용 순서가 이전과 같다.
                    int forced = Mathf.RoundToInt(p.GetWithDefault("training_layout", -1f));
                    if (forced >= 0 && rng.NextDouble() < p.GetWithDefault("training_layout_prob", 1f))
                        layout = forced;
                    else
                        layout = CampaignProgress.DrawLayout(rng, lastCampaignLayouts[level] - 1);
                    lastCampaignLayouts[level] = layout + 1;
                }
            }
            // 방 번호는 배치 선택에만 영향을 주고, 선택한 배치의 기하는 캠페인과 동일하다.
            if (layout >= 0) rng = new System.Random(layout * 1000 + level);
            obsMode = Mathf.RoundToInt(p.GetWithDefault("obs_mode", 1f));
            time = 0f;
            pos = new Vector3(Rand(-2.5f, 2.5f), 0f, StartZ);
            vel = Vector3.zero;
            grounded = true;
            crouch = false;
            slideTimer = 0f;
            int level6Design = Mathf.Clamp(Mathf.RoundToInt(
                p.GetWithDefault("level6_design", DefaultLevel6Design)), 0, 3);
            GenerateLasers(level, level6Design);
            if (layout >= 0)
            {
                // 같은 위치의 벽 양쪽을 함께 이동해 통로가 어긋나지 않게 한다.
                var shifts = new Dictionary<float, float>();
                float speed = Rand(0.94f, 1.06f);
                float gapBonus = Mathf.Clamp(p.GetWithDefault("training_gap_bonus", 0f), 0f, 0.5f);
                for (int i = 0; i < lasers.Count; i++)
                {
                    var laser = lasers[i];
                    if (!shifts.TryGetValue(laser.z0, out float shift))
                    {
                        shift = Rand(-0.22f, 0.22f);
                        shifts.Add(laser.z0, shift);
                    }
                    laser.z0 += shift;
                    laser.omega *= speed;
                    if (laser.side != 0) laser.gapHalf += gapBonus;
                    if (laser.kind == LaserKind.Blinker)
                    {
                        laser.period /= speed;
                        laser.phase += Rand(-0.10f, 0.10f);
                    }
                    lasers[i] = laser;
                }
            }
            else
            {
                // 학습 전용: 무작위 배치에서도 통로 넓히기 커리큘럼을 쓸 수 있게 한다 (기본값 0이면 변화 없음, 난수도 쓰지 않음).
                float gapBonus = Mathf.Clamp(p.GetWithDefault("training_gap_bonus", 0f), 0f, 0.5f);
                if (gapBonus > 0f)
                    for (int i = 0; i < lasers.Count; i++)
                    {
                        var laser = lasers[i];
                        if (laser.side != 0) { laser.gapHalf += gapBonus; lasers[i] = laser; }
                    }
            }
            rng = practiceRng;
            prevPos = pos;
            prevCrouch = crouch;
            prevTime = time;
        }

        float Rand(float a, float b) => a + (float)rng.NextDouble() * (b - a);
        float Sign() => rng.Next(2) == 0 ? -1f : 1f;

        // ------------------------------------------------------------------
        // 레벨: 레이저 배치
        // ------------------------------------------------------------------
        void GenerateLasers(int lv, int level6Design)
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
                case 5:
                {
                    // 6개 구간: 겹친 레이저 2(막대+좌우 막대), 레이저 벽 2(움직이는 통로), 회전, 깜빡임. 순서는 무작위
                    var parts = new List<int> { 0, 0, 1, 1, 2, 3 };
                    Shuffle(parts);
                    float[] slots = { -6.3f, -3.8f, -1.3f, 1.2f, 3.7f, 6.2f };
                    for (int i = 0; i < 6; i++)
                    {
                        float z = slots[i] + Rand(-0.15f, 0.15f);
                        switch (parts[i])
                        {
                            case 0:   // 높이에 맞춰 점프/슬라이딩하면서, 같은 자리를 쓸고 가는 세로 막대도 피해야 한다
                                lasers.Add(MakeBar(z, moving: false));
                                lasers.Add(MakeSweeper(z, 1f));
                                break;
                            case 1:
                                AddWall(z, 1.2f);
                                break;
                            default:
                                lasers.Add(Make(parts[i] == 2 ? LaserKind.Rotor : LaserKind.Blinker, z, 1.4f));
                                break;
                        }
                    }
                    break;
                }
                case 6:
                {
                    // 6개 구간, 레이저 12개. 레벨 5보다 여유가 작고, 기다렸다가 움직이는 판단이 필요하다
                    //  0 이중 벽: 1.1m 간격의 벽 두 개, 통로가 서로 반대로 움직인다 (두 벽 사이에서 기다렸다 옆으로 가야 함)
                    //  1 좁은 벽: 통로 폭 1.1m (에이전트 폭 0.6m), 빠르게 움직인다
                    //  2 깜빡이는 벽: 통로 없이 막혔다가 잠깐 꺼진다
                    //  3 움직이는 겹친 레이저: 앞뒤로 움직이는 막대 + 세로 막대 (2곳)
                    //  4 빠른 회전 막대
                    var parts = new List<int> { 0, 1, 2, 3, 3, 4 };
                    Shuffle(parts);
                    float[] slots = { -6.6f, -4.1f, -1.6f, 0.9f, 3.4f, 5.9f };
                    for (int i = 0; i < 6; i++)
                    {
                        float z = slots[i] + Rand(-0.1f, 0.1f);
                        switch (parts[i])
                        {
                            case 0:
                            {
                                float center = Rand(-0.5f, 0.5f), amp = Rand(1.8f, 2.4f);
                                float omega = Rand(0.8f, 1.1f), phase = Rand(0f, 6.283f);
                                // Leave enough depth to stop between the walls even after layout jitter.
                                float offset = level6Design >= 1 ? 0.72f : 0.55f;
                                AddWall(z - offset, center, amp, omega, phase, gapHalf: 0.75f);
                                AddWall(z + offset, center, amp, omega, phase + Mathf.PI, gapHalf: 0.75f);
                                break;
                            }
                            case 1:
                            {
                                float center = Rand(-1f, 1f), amplitude = Rand(1.5f, 2.3f);
                                float omega = Rand(1.1f, 1.5f), phase = Rand(0f, 6.283f);
                                if (level6Design >= 3) omega = Mathf.Min(omega, 2.1f / amplitude);
                                AddWall(z, center, amplitude, omega, phase, level6Design >= 2 ? 0.68f : 0.55f);
                                break;
                            }
                            case 2:
                                lasers.Add(new Laser { kind = LaserKind.Blinker, z0 = z, fullWidthWall = true, height = Laser.WallHeight,
                                    period = Rand(1.8f, 2.4f), duty = 0.65f, phase = Rand(0f, 1f) });
                                break;
                            case 3:
                                lasers.Add(MakeBar(z, moving: true, 1.3f));
                                lasers.Add(MakeSweeper(z, 1.15f));
                                break;
                            default:
                                lasers.Add(Make(LaserKind.Rotor, z, 1.6f));
                                break;
                        }
                    }
                    break;
                }
                case 7:
                    AddWall(-5.6f, -0.7f, 1.8f, 1.05f, 0f, 0.62f);
                    AddWall(-2.4f, 0.7f, 1.9f, 1.2f, 1.6f, 0.62f);
                    lasers.Add(Make(LaserKind.Rotor, 0.7f, 1.25f));
                    AddWall(4.0f, 0f, 2.4f, 1.2f, 3.2f, 0.58f);
                    lasers.Add(MakeSweeper(6.4f, 1.3f));
                    break;
                case 8:
                    AddTimedWall(-5.8f, 2.4f, 0.60f, 0.05f);
                    lasers.Add(MakeBar(-3.3f, moving: false));
                    AddTimedWall(-0.5f, 2.6f, 0.67f, 0.45f);
                    AddWall(2.1f, 0f, 2.0f, 1.1f, 2.1f, 0.65f);
                    AddTimedWall(5.4f, 2.5f, 0.68f, 0.75f);
                    lasers.Add(MakeSweeper(7.0f, 1.1f));
                    break;
                case 9:
                    AddWall(-5.8f, 0f, 1.9f, 1.0f, 0f, 0.68f);
                    AddWall(-4.4f, 0f, 1.9f, 1.0f, Mathf.PI, 0.68f);
                    lasers.Add(MakeBar(-1.5f, moving: true));
                    lasers.Add(MakeSweeper(0.3f, 1.35f));
                    AddWall(3.4f, 0.4f, 2.1f, 1.15f, 0.8f, 0.67f);
                    AddWall(4.8f, 0.4f, 2.1f, 1.15f, 0.8f + Mathf.PI, 0.67f);
                    AddTimedWall(7.0f, 2.4f, 0.64f, 0.3f);
                    break;
                case 10:
                    AddTimedWall(-6.2f, 2.5f, 0.68f, 0.12f);
                    AddWall(-3.8f, -0.3f, 2.1f, 1.15f, 0.3f, 0.65f);
                    AddWall(-2.4f, -0.3f, 2.1f, 1.15f, 0.3f + Mathf.PI, 0.65f);
                    lasers.Add(Make(LaserKind.Rotor, 0.65f, 1.4f));
                    lasers.Add(MakeSweeper(2.7f, 1.3f));
                    AddWall(4.6f, 0.1f, 2.35f, 1.35f, 2.1f, 0.56f);
                    AddTimedWall(7.0f, 2.6f, 0.72f, 0.57f);
                    break;
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

        /// <summary>레이저 벽: 폭 1.6m 통로 하나만 열려 있고, 통로가 좌우로 움직인다.</summary>
        void AddWall(float z, float speed) =>
            AddWall(z, Rand(-1f, 1f), Rand(1.2f, 2.2f), Rand(0.7f, 1.2f) * speed, Rand(0f, 6.283f), 0.8f);

        void AddWall(float z, float center, float amp, float omega, float phase, float gapHalf)
        {
            foreach (int sd in new[] { -1, 1 })
                lasers.Add(new Laser { kind = LaserKind.Bar, z0 = z, side = sd, gapCenter = center, gapAmp = amp,
                    gapHalf = gapHalf, omega = omega, phase = phase });
        }

        void AddTimedWall(float z, float period, float duty, float phase) =>
            lasers.Add(new Laser { kind = LaserKind.Blinker, z0 = z, fullWidthWall = true,
                height = Laser.WallHeight, period = period, duty = duty, phase = phase });

        Laser MakeBar(float z, bool moving, float speed = 1f) => new Laser
        {
            kind = LaserKind.Bar, z0 = z, height = rng.Next(2) == 0 ? 0.35f : 1.35f,
            amp = moving ? 1f : 0f, omega = Rand(1f, 2f) * speed, phase = Rand(0f, 6.283f),
        };

        Laser MakeSweeper(float z, float speed) => new Laser
        {
            kind = LaserKind.Sweeper, z0 = z, omega = Rand(1.2f, 2f) * speed, phase = Rand(0f, 6.283f),
        };
    }
}
