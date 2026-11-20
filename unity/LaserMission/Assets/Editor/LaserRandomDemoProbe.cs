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

/// <summary>무작위 배치에서 빔 탐색 시범과 '벗어났다 돌아오는' 회복 시범을 (관측, 행동) 쌍으로 저장한다 (11장 슬라이드 12).</summary>
public static class LaserRandomDemoProbe
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

    static List<State> Chain(State goal)
    {
        var list = new List<State>();
        for (var s = goal; s != null; s = s.Parent) list.Add(s);
        list.Reverse();
        return list;                       // list[0] = 시작 상태, list[k+1] = k번째 행동 뒤
    }

    static void Record(Room room, List<State> chain, List<string> output, int stage, int seed, string tag)
    {
        var obs = new List<float>();
        for (int k = 0; k + 1 < chain.Count; k++)
        {
            Restore(room, chain[k]);
            obs.Clear();
            room.Observe(obs);
            output.Add($"{stage},{seed},{tag},{chain[k + 1].Action}," +
                       string.Join(" ", obs.Select(v => v.ToString("R", CultureInfo.InvariantCulture))));
        }
    }

    public static void Run()
    {
        var args = Environment.GetCommandLineArgs();
        int stage = 6, layouts = 300, recoveries = 2;
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "-demoStage") stage = int.Parse(args[i + 1]);
            if (args[i] == "-demoLayouts") layouts = int.Parse(args[i + 1]);
            if (args[i] == "-demoRecoveries") recoveries = int.Parse(args[i + 1]);
        }
        var room = new GameObject("Random demo probe").AddComponent<Room>();
        var rngField = typeof(Room).GetField("rng", BindingFlags.Instance | BindingFlags.NonPublic);
        var noise = new System.Random(stage);
        var output = new List<string> { "stage,seed,kind,action,obs" };
        int solved = 0, recovered = 0;
        Room.DefaultLevel = stage;
        for (int seed = 0; seed < layouts; seed++)
        {
            rngField.SetValue(room, new System.Random(2_000_000 + stage * 10_000 + seed));
            room.Campaign = null;
            room.ResetEpisode();
            Require(room.level == stage, "Unexpected level");
            var start = Save(room);
            var goal = Find(room, start, 128) ?? Find(room, start, 384);
            if (goal == null) continue;
            solved++;
            var chain = Chain(goal);
            Record(room, chain, output, stage, seed, "demo");
            // 회복 시범: 경로 중간에서 무작위 행동 몇 번으로 벗어난 뒤 다시 경로를 찾는다
            for (int r = 0; r < recoveries; r++)
            {
                int k = noise.Next(1, Math.Max(2, chain.Count - 5));
                Restore(room, chain[k]);
                State off = Save(room);
                bool alive = true;
                int pushes = noise.Next(2, 6);
                for (int j = 0; j < pushes && alive; j++)
                {
                    int a = noise.Next(Room.NumActions);
                    alive = room.Step(a, out _) == Outcome.None;
                    off = Save(room, off, a);
                }
                if (!alive) continue;
                off.Parent = null;
                var back = Find(room, off, 128) ?? Find(room, off, 384);
                if (back == null) continue;
                recovered++;
                Record(room, Chain(back), output, stage, seed, "recovery");
            }
        }
        System.IO.File.WriteAllLines($"../../laser/data/random_demos_l{stage}.csv", output);
        Debug.Log($"Random demo probe stage {stage}: {solved}/{layouts} solved, {recovered} recoveries, {output.Count - 1} pairs");
    }
}
