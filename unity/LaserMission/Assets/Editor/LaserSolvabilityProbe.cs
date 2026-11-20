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
}
