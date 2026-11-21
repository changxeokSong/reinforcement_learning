using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using LaserMission;
using UnityEngine;
using Unity.MLAgents.Actuators;
using Outcome = LaserMission.Room.Outcome;

/// <summary>무작위 배치(캠페인 배치 끔)가 통과 가능한지 빔 탐색으로 확인한다. 학습 정책 성공률의 상한을 추정한다.</summary>
public static class LaserSolvabilityProbe
{
    sealed class State
    {
        public Vector3 Position, Velocity;
        public bool Grounded, Crouch;
        public float Time, Slide;
        public State Parent;
        public int Action;
    }

    static State Save(Room room, State parent = null, int action = -1) => new State
    {
        Position = room.pos, Velocity = room.vel, Grounded = room.grounded, Crouch = room.crouch,
        Time = room.time, Slide = room.slideTimer, Parent = parent, Action = action,
    };

    static void Restore(Room room, State state)
    {
        room.pos = state.Position;
        room.vel = state.Velocity;
        room.grounded = state.Grounded;
        room.crouch = state.Crouch;
        room.time = state.Time;
        room.slideTimer = state.Slide;
    }

    static int Quantize(float value, float size) => Mathf.RoundToInt(value / size);

    static State Find(Room room, State start, int beamSize)
    {
        var beam = new List<State> { start };
        for (int tick = 0; tick < 200 && beam.Count > 0; tick++)
        {
            var visited = new HashSet<(int, int, int, int)>();
            var next = new List<State>();
            foreach (var state in beam)
            {
                for (int action = 0; action < Room.NumActions; action++)
                {
                    Restore(room, state);
                    var outcome = room.Step(action, out _);
                    if (outcome == Outcome.Goal) return Save(room, state, action);
                    if (outcome != Outcome.None) continue;
                    var key = (Quantize(room.pos.x, 0.10f), Quantize(room.pos.z, 0.12f),
                        Quantize(room.vel.y, 0.25f), Quantize(Mathf.Max(room.slideTimer, 0f), 0.08f));
                    if (visited.Add(key)) next.Add(Save(room, state, action));
                }
            }
            var perDepth = new Dictionary<int, int>();
            beam.Clear();
            foreach (var state in next.OrderByDescending(s => s.Position.z))
            {
                int depth = Quantize(state.Position.z, 0.4f);
                perDepth.TryGetValue(depth, out int count);
                if (count >= Mathf.Max(36, beamSize / 10)) continue;
                perDepth[depth] = count + 1;
                beam.Add(state);
                if (beam.Count >= beamSize) break;
            }
        }
        return null;
    }


    static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    static void Act(LaserAgent agent, int action) =>
        agent.OnActionReceived(new ActionBuffers(Array.Empty<float>(), new[] {action}));


    static string Layout(Room room) => string.Join(";", room.lasers.Select(l =>
        $"{l.z0:R}/{l.height:R}/{l.phase:R}/{l.omega:R}/{l.gapCenter:R}/{l.period:R}"));

    public static void Run()
    {
        var room = new GameObject("Solvability probe").AddComponent<Room>();
        var rngField = typeof(Room).GetField("rng", BindingFlags.Instance | BindingFlags.NonPublic);
        var output = new List<string> { "stage,seed,solvable,seconds" };
        const int perStage = 30;
        for (int stage = 1; stage <= Room.MaxLevel; stage++)
        {
            Room.DefaultLevel = stage;
            int solved = 0;
            for (int seed = 0; seed < perStage; seed++)
            {
                rngField.SetValue(room, new System.Random(1_000_000 + stage * 1000 + seed));
                room.Campaign = null;
                room.ResetEpisode();
                Require(room.level == stage, $"Unexpected level {room.level}");
                var start = Save(room);
                var goal = Find(room, start, 128) ?? Find(room, start, 384) ?? Find(room, start, 1024);
                string seconds = "";
                if (goal != null)
                {
                    solved++;
                    float t = goal.Time;
                    seconds = t.ToString("F2", CultureInfo.InvariantCulture);
                }
                output.Add($"{stage},{seed},{(goal != null ? 1 : 0)},{seconds}");
            }
            Debug.Log($"Stage {stage}: {solved}/{perStage} random layouts solvable");
        }
        System.IO.File.WriteAllLines("../../laser/data/random_layout_solvability.csv", output);
    }

    static bool Replay(Room room, State start, List<int> actions, float shift, int pause)
    {
        Restore(room, start);
        room.pos += Vector3.right * shift;
        for (int i = 0; i < actions.Count; i++)
        {
            if (i == pause && room.Step(4, out _) != Outcome.None) return false;
            var outcome = room.Step(actions[i], out _);
            if (outcome != Outcome.None) return outcome == Outcome.Goal;
        }
        return false;
    }

    static void CheckRotor(Room room)
    {
        const float tolerance = 0.0001f;
        var rotor = new Laser { kind = LaserKind.Rotor, height = 0.35f, omega = 1.5f };
        rotor.Segment(0f, out var left, out var right);
        Require(Mathf.Abs(left.x + Room.HalfWidth) < tolerance &&
            Mathf.Abs(right.x - Room.HalfWidth) < tolerance, "Crosswise rotor must reach both walls");
        for (int i = 0; i < 48; i++)
        {
            rotor.z0 = i % 2 == 0 ? -8f : 8f;
            rotor.Segment(i * 0.1f, out var a, out var b);
            foreach (var end in new[] { a, b })
                Require(Mathf.Abs(end.x) <= Room.HalfWidth + tolerance &&
                    Mathf.Abs(end.z) <= Room.HalfLength + tolerance &&
                    Mathf.Abs(end.z - rotor.z0) <= Laser.RotorDepthReach + tolerance,
                    "Rotor endpoint escaped its bounds");
        }

        rotor.z0 = 0f;
        var initial = new State { Grounded = true };
        foreach (float height in new[] { 0.35f, 1.35f })
        {
            rotor.height = height;
            rotor.phase = -0.1f * rotor.omega;
            room.lasers.Clear();
            room.lasers.Add(rotor);
            foreach (int side in new[] { -1, 1 })
            {
                initial.Position = new Vector3(side * (Room.HalfWidth - Room.AgentRadius), 0f, -0.4f);
                Restore(room, initial);
                Require(room.Step(7, out _) == Outcome.Hit, "Standing edge approach bypassed a crosswise rotor");
            }

            rotor.omega = 0.35f;
            rotor.phase = -0.35f * rotor.omega;
            room.lasers[0] = rotor;
            initial.Position = new Vector3(0f, 0f, -1.4f);
            Restore(room, initial);
            int dodge = height < 1f ? 16 : 25;
            for (int i = 0; i < 5; i++)
                Require(room.Step(i == 0 ? dodge : 7, out _) == Outcome.None, "Timed jump or slide failed");
            Require(room.pos.z > 0.5f, "Dodge did not cross the beam");
            rotor.omega = 1.5f;
        }
        Debug.Log("Rotor audit: blocked all four standing edge approaches; timed jump and slide passed.");
    }

    public static void RunRotorAudit()
    {
        string[] args = Environment.GetCommandLineArgs();
        int outputArg = Array.IndexOf(args, "-rotor-audit-output");
        Require(outputArg >= 0 && outputArg + 1 < args.Length, "Missing -rotor-audit-output");
        int countArg = Array.IndexOf(args, "-rotor-audit-count");
        int count = countArg < 0 ? 20 : int.Parse(args[countArg + 1], CultureInfo.InvariantCulture);
        Require(count > 0, "Expected a positive procedural layout count");
        int stagesArg = Array.IndexOf(args, "-rotor-audit-stages");
        var stages = stagesArg < 0 ? new[] { 3, 4, 5, 6, 7, 10 }
            : args[stagesArg + 1].Split(',').Select(value => int.Parse(value, CultureInfo.InvariantCulture)).ToArray();
        Require(stages.All(stage => stage >= 1 && stage <= Room.MaxLevel), "Invalid audit stages");
        var room = new GameObject("Rotor audit").AddComponent<Room>();
        CheckRotor(room);
        var rngField = typeof(Room).GetField("rng", BindingFlags.Instance | BindingFlags.NonPublic);
        Room.DefaultLevel6Design = 2;
        var rows = new List<string> { "stage,layout,seed,rotors,solvable,seconds" };
        foreach (int stage in stages)
        {
            for (int seed = 0; seed < count + CampaignProgress.LayoutCount; seed++)
            {
                bool campaign = seed >= count;
                int layoutSeed = campaign ? seed - count : 1_070_000 + stage * 1000 + seed;
                ResetAuditLayout(room, rngField, stage, layoutSeed, campaign);
                var start = Save(room);
                var goal = Find(room, start, 128) ?? Find(room, start, 384) ?? Find(room, start, 1024);
                if (goal != null)
                {
                    var actions = new List<int>();
                    for (var state = goal; state.Parent != null; state = state.Parent) actions.Add(state.Action);
                    actions.Reverse();
                    Require(Replay(room, start, actions, 0, -1), "Rotor audit path did not replay");
                }
                int rotors = room.lasers.Count(laser => laser.kind == LaserKind.Rotor);
                string seconds = goal == null ? "" : goal.Time.ToString("F3", CultureInfo.InvariantCulture);
                rows.Add($"{stage},{(campaign ? "campaign" : "procedural")},{layoutSeed},{rotors},{(goal != null ? 1 : 0)},{seconds}");
            }
            Debug.Log($"Rotor audit completed stage {stage}");
            File.WriteAllLines(args[outputArg + 1], rows);
        }
    }

    static void ResetAuditLayout(Room room, FieldInfo rngField, int stage, int seed, bool campaign)
    {
        Room.DefaultLevel = stage;
        rngField.SetValue(room, new System.Random(seed));
        room.Campaign = campaign ? new CampaignProgress(seed) : null;
        for (int level = 1; campaign && level < stage; level++)
        {
            room.Campaign.Finish(Outcome.Goal);
            room.Campaign.Continue();
        }
        room.ResetEpisode();
        Require(room.level == stage, $"Expected stage {stage}");
    }

    public static void RunCampaignModesAudit()
    {
        var room = new GameObject("Campaign modes audit").AddComponent<Room>();
        var rngField = typeof(Room).GetField("rng", BindingFlags.Instance | BindingFlags.NonPublic);
        var observed = new HashSet<(float, string)>();
        var replay = new List<(float, string)>();
        for (int run = 0; run < 2; run++)
        {
            room.Campaign = new CampaignProgress(716, procedural: true);
            rngField.SetValue(room, new System.Random(716_000));
            for (int attempt = 0; attempt < 24; attempt++)
            {
                room.ResetEpisode();
                Require(room.level == 1 && room.Campaign.LayoutSeed == -1, "Expected a procedural stage 1");
                Require(room.Campaign.Attempt == attempt + 1, "Retry count did not advance");
                var current = (room.pos.x, Layout(room));
                if (run == 0)
                {
                    Require(observed.Add(current), "Procedural retry repeated its layout");
                    replay.Add(current);
                }
                else Require(current == replay[attempt], "A campaign seed did not reproduce the same retry sequence");
                room.Campaign.Finish(Outcome.Hit);
                room.Campaign.Continue();
            }
            for (int stage = 1; stage <= Room.MaxLevel; stage++)
            {
                room.ResetEpisode();
                Require(room.level == stage, "Campaign failed to advance");
                if (stage > 1) Require(room.Campaign.Attempt == 1, "A new stage inherited the previous attempt count");
                room.Campaign.Finish(Outcome.Goal);
                if (stage < Room.MaxLevel) room.Campaign.Continue();
            }
            Require(room.Campaign.CurrentPhase == CampaignProgress.Phase.Complete, "Stage 10 did not finish the campaign");
        }
        Debug.Log("Campaign audit: 24 distinct procedurally generated attempts, seed replay, and stage 10 completion passed.");
    }

    public static void RunLaserBoundsAudit()
    {
        const float tolerance = 0.0001f;
        const int proceduralCount = 20;
        var room = new GameObject("Laser bounds audit").AddComponent<Room>();
        var rngField = typeof(Room).GetField("rng", BindingFlags.Instance | BindingFlags.NonPublic);
        Room.DefaultLevel6Design = 3;
        int checkedLayouts = 0;
        for (int stage = 1; stage <= Room.MaxLevel; stage++)
        {
            for (int i = 0; i < proceduralCount + CampaignProgress.LayoutCount; i++)
            {
                bool campaign = i >= proceduralCount;
                int seed = campaign ? i - proceduralCount : 1_080_000 + stage * 1000 + i;
                ResetAuditLayout(room, rngField, stage, seed, campaign);
                foreach (var laser in room.lasers)
                {
                    if (laser.side != 0)
                        Require(Mathf.Abs(laser.gapCenter) + laser.gapAmp + laser.gapHalf <= Room.HalfWidth + tolerance,
                            $"Stage {stage}: a moving gap can leave the room");
                    if (laser.kind == LaserKind.Sweeper)
                    {
                        float peakTime = (Mathf.PI / 2f - laser.phase) / laser.omega;
                        laser.Segment(peakTime, out var right, out _);
                        laser.Segment(peakTime + Mathf.PI / laser.omega, out var left, out _);
                        float playerEdge = Room.HalfWidth - Room.AgentRadius;
                        Require(Mathf.Abs(right.x - playerEdge) < tolerance && Mathf.Abs(left.x + playerEdge) < tolerance,
                            $"Stage {stage}: sweeper does not reach both player edges");
                    }
                    for (int tick = 0; tick < 48; tick++)
                    {
                        laser.Segment(tick * 0.1f, out var a, out var b);
                        Require(Mathf.Max(Mathf.Abs(a.x), Mathf.Abs(b.x)) <= Room.HalfWidth + tolerance &&
                            Mathf.Max(Mathf.Abs(a.z), Mathf.Abs(b.z)) <= Room.HalfLength + tolerance,
                            $"Stage {stage}: {laser.kind} escaped the room");
                        if (laser.kind == LaserKind.Blinker || laser.kind == LaserKind.Bar && laser.side == 0)
                            Require(Mathf.Abs(a.x + Room.HalfWidth) < tolerance && Mathf.Abs(b.x - Room.HalfWidth) < tolerance,
                                $"Stage {stage}: {laser.kind} leaves an edge gap");
                        if (laser.side != 0)
                        {
                            float outerX = laser.side < 0 ? a.x : b.x;
                            Require(Mathf.Abs(outerX - laser.side * Room.HalfWidth) < tolerance,
                                $"Stage {stage}: moving gate detached from its wall");
                        }
                    }
                }
                checkedLayouts++;
            }
        }
        Debug.Log($"Laser bounds audit passed: {checkedLayouts} layouts across all {Room.MaxLevel} stages.");
    }

    public static void RunLevel6Audit()
    {
        string[] args = Environment.GetCommandLineArgs();
        int outputArg = Array.IndexOf(args, "-level6-audit-output");
        Require(outputArg >= 0 && outputArg + 1 < args.Length, "Missing -level6-audit-output");
        string path = args[outputArg + 1];
        int designArg = Array.IndexOf(args, "-level6-audit-design");
        int countArg = Array.IndexOf(args, "-level6-audit-count");
        int firstDesign = designArg < 0 ? 0 : int.Parse(args[designArg + 1], CultureInfo.InvariantCulture);
        int lastDesign = designArg < 0 ? 2 : firstDesign;
        int proceduralCount = countArg < 0 ? 60 : int.Parse(args[countArg + 1], CultureInfo.InvariantCulture);
        Require(firstDesign >= 0 && lastDesign <= 3 && proceduralCount > 0, "Invalid design or layout count");
        var room = new GameObject("Level 6 design audit").AddComponent<Room>();
        var rngField = typeof(Room).GetField("rng", BindingFlags.Instance | BindingFlags.NonPublic);
        Room.DefaultLevel = 6;
        var rows = new List<string> { "design,layout,seed,wait_margin_m,narrow_clearance_m,found,seconds,spawn_survived,pause_survived" };
        for (int design = firstDesign; design <= lastDesign; design++)
        {
            Room.DefaultLevel6Design = design;
            for (int seed = 0; seed < proceduralCount + 4; seed++)
            {
                bool campaign = seed >= proceduralCount;
                rngField.SetValue(room, new System.Random(1_006_000 + seed));
                if (campaign)
                {
                    room.Campaign = new CampaignProgress(seed - proceduralCount);
                    for (int level = 1; level < 6; level++)
                    {
                        room.Campaign.Finish(Outcome.Goal);
                        room.Campaign.Continue();
                    }
                }
                else room.Campaign = null;
                room.ResetEpisode();
                Require(room.level == 6, "Expected level 6");
                var walls = room.lasers.Where(l => l.side < 0).ToArray();
                var pair = walls.Where(l => Mathf.Abs(l.gapHalf - 0.75f) < 0.001f).OrderBy(l => l.z0).ToArray();
                Require(pair.Length == 2 && walls.Length == 3, "Unexpected wall layout");
                float radius = Room.AgentRadius + Laser.WallHalfThickness;
                float margin = pair[1].z0 - pair[0].z0 - 2 * radius;
                var narrow = walls.OrderBy(l => l.gapHalf).First();
                float clearance = 2 * (narrow.gapHalf - radius);
                if (design > 0 && campaign) Require(margin >= 0.28f, "Double-wall waiting depth too small");
                if (design == 3) Require(narrow.gapAmp * narrow.omega <= 2.1f * (campaign ? 1.06f : 1f) + 0.001f,
                    "Narrow gate exceeded the speed limit");
                var start = Save(room);
                var goal = Find(room, start, 128) ?? Find(room, start, 384) ?? Find(room, start, 1024);
                int spawnSurvived = 0, pauseSurvived = 0;
                if (goal != null)
                {
                    var actions = new List<int>();
                    for (var state = goal; state.Parent != null; state = state.Parent) actions.Add(state.Action);
                    actions.Reverse();
                    Require(Replay(room, start, actions, 0, -1), "Search path did not replay");
                    foreach (float shift in new[] { -0.1f, 0.1f })
                        if (Replay(room, start, actions, shift, -1)) spawnSurvived++;
                    foreach (int fraction in new[] { 1, 2, 3 })
                        if (Replay(room, start, actions, 0, actions.Count * fraction / 4)) pauseSurvived++;
                }
                string seconds = goal == null ? "" : goal.Time.ToString("F3", CultureInfo.InvariantCulture);
                rows.Add(FormattableString.Invariant(
                    $"{design},{(campaign ? "campaign" : "procedural")},{(campaign ? seed - proceduralCount : seed)},{margin:F5},{clearance:F5},{(goal != null ? 1 : 0)},{seconds},{spawnSurvived},{pauseSurvived}"));
            }
            File.WriteAllLines(path, rows);
            Debug.Log($"Completed level 6 audit design {design}");
        }
    }
}
