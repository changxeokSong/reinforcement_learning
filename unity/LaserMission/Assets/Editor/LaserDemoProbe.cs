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

/// <summary>단계·배치마다 통과 경로를 빔 탐색으로 찾아 행동 순서를 저장한다 (모방 학습의 시범 데이터).</summary>
public static class LaserDemoProbe
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
        var room = new GameObject("Demo probe").AddComponent<Room>();
        typeof(Room).GetField("rng", BindingFlags.Instance | BindingFlags.NonPublic)
            .SetValue(room, new System.Random(0));
        var actorObject = new GameObject("Demo probe agent");
        actorObject.SetActive(false);
        var actor = actorObject.AddComponent<LaserAgent>();
        actor.room = room;
        var output = new List<string> { "stage,layout,seconds,actions" };
        for (int variant = 0; variant < CampaignProgress.LayoutCount; variant++)
        {
            var campaign = new CampaignProgress(variant);
            room.Campaign = campaign;
            for (int stage = 1; stage <= Room.MaxLevel; stage++)
            {
                room.ResetEpisode();
                Require(room.level == stage && campaign.LayoutSeed == variant, "Unexpected layout");
                var start = Save(room);
                var goal = Find(room, start, 128) ?? Find(room, start, 384) ?? Find(room, start, 1024);
                Require(goal != null, $"No path at stage {stage}, layout {variant}");
                var path = new List<int>();
                for (var state = goal; state.Parent != null; state = state.Parent) path.Add(state.Action);
                path.Reverse();
                Restore(room, start);
                foreach (int action in path) Act(actor, action);
                var expected = stage == Room.MaxLevel ? CampaignProgress.Phase.Complete : CampaignProgress.Phase.StageCleared;
                Require(campaign.CurrentPhase == expected, $"Replay failed at stage {stage}, layout {variant}");
                output.Add($"{stage},{variant},{room.time.ToString("F2", CultureInfo.InvariantCulture)},{string.Join(" ", path)}");
                campaign.Continue();
            }
        }
        System.IO.File.WriteAllLines("../../laser/data/campaign_demos.csv", output);
        Debug.Log($"Demo probe saved {output.Count - 1} paths.");
    }
}
