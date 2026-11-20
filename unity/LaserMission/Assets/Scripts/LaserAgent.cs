using System.Collections.Generic;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;
using UnityEngine;

namespace LaserMission
{
    /// <summary>
    /// ML-Agents와 Room을 잇는다. 보상: 금고 도착 +1, 레이저 -1, 시간 초과 -1, 매 결정 -0.01(시간 벌점).
    /// 보조 보상: 금고 쪽으로 다가간 거리에 비례 (출발선→금고 전체가 shaping 값만큼).
    /// </summary>
    public class LaserAgent : Agent
    {
        public Room room;
        readonly List<float> buffer = new List<float>(Room.ObsSize);

        public override void OnEpisodeBegin() => room.ResetEpisode();

        public override void CollectObservations(VectorSensor sensor)
        {
            buffer.Clear();
            room.Observe(buffer);
            sensor.AddObservation(buffer);
        }

        public override void OnActionReceived(ActionBuffers actions)
        {
            if (room.Campaign != null)
            {
                if (room.Campaign.CurrentPhase == CampaignProgress.Phase.Playing)
                    room.Campaign.Finish(room.Step(actions.DiscreteActions[0], out _));
                return;
            }
            int a = actions.DiscreteActions[0];
            float oldZ = room.pos.z;
            var outcome = room.Step(a, out float progress);
            var parameters = Academy.Instance.EnvironmentParameters;
            float shaping = parameters.GetWithDefault("shaping", 0.5f);
            if (parameters.GetWithDefault("potential_shaping", 0f) > 0.5f)
            {
                float gamma = parameters.GetWithDefault("shaping_gamma", 0.99f);
                float nextPotential = outcome == Room.Outcome.None ? DistancePotential(room.pos.z) : 0f;
                AddReward(shaping * (gamma * nextPotential - DistancePotential(oldZ)));
            }
            else
            {
                AddReward(shaping * progress);
            }
            // 시간 벌점: 제자리에서 버티는 비용이 바로 느껴지게 한다 (할인율 때문에 끝의 -1만으로는 부족하다)
            AddReward(-parameters.GetWithDefault("time_penalty", 0.01f));
            switch (outcome)
            {
                case Room.Outcome.Goal:
                    AddReward(1f);
                    EndEpisode();
                    break;
                case Room.Outcome.Hit:
                    AddReward(-1f);
                    EndEpisode();
                    break;
                case Room.Outcome.Timeout:
                    // 시간 초과도 실패다. 0점으로 두면 "레이저 앞에서 멈춰 있기"가 가장 안전한 전략이 된다
                    AddReward(-1f);
                    EndEpisode();
                    break;
            }
        }

        // 금고에서 0, 출발점에서 -1인 정규화 거리.
        static float DistancePotential(float z) => (z - Room.GoalZ) / (Room.GoalZ - Room.StartZ);

        /// <summary>Python 없이 실행하면 키보드로 조작한다. WASD 이동, Space 점프, C/Ctrl 슬라이딩(숙이기).</summary>
        public override void Heuristic(in ActionBuffers actionsOut)
        {
            int mx = 1, mz = 1, v = 0;
            if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) mx = 0;
            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) mx = 2;
            if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) mz = 0;
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) mz = 2;
            if (Input.GetKey(KeyCode.C) || Input.GetKey(KeyCode.LeftControl)) v = 2;
            if (Input.GetKey(KeyCode.Space)) v = 1;
            var d = actionsOut.DiscreteActions;
            d[0] = mx + 3 * mz + 9 * v;
        }
    }
}
