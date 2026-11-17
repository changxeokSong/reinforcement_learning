using System.Collections.Generic;
using UnityEngine;

namespace LaserMission
{
    /// <summary>
    /// 실행하면 방을 만든다. 학습할 때는 Python이 "-areas 16"처럼 방 개수를 넘겨서
    /// 한 프로세스 안에서 여러 판을 동시에 진행한다. 화면에는 0번 방이 보인다.
    ///
    /// 키: 0~4 레벨 바꾸기(Python 없이 실행할 때), V 카메라 바꾸기, R 다시 시작
    /// </summary>
    public class Bootstrap : MonoBehaviour
    {
        public Room.Materials materials;
        public Camera cam;
        public int areas = 1;
        public float spacing = 12f;

        readonly List<Room> rooms = new List<Room>();
        int view;                       // 0 위에서 비스듬히, 1 뒤에서 따라가기, 2 옆에서
        GUIStyle big, small;
        string shotPath;                // -shot 경로: 화면을 찍고 종료한다 (보고서·확인용)
        float shotDelay = 4f;
        int shotCount = 1, shotsTaken;

        void Awake()
        {
            // 결정 한 번이 게임 시간 0.1초다. 시간 배속 1이면 실제 시간과 같은 속도로 보인다
            Time.fixedDeltaTime = 0.1f;
            Application.targetFrameRate = 60;
            int seed = 0;
            var args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "-areas") int.TryParse(args[i + 1], out areas);
                if (args[i] == "-envseed") int.TryParse(args[i + 1], out seed);
                if (args[i] == "-level" && int.TryParse(args[i + 1], out int lv)) Room.DefaultLevel = lv;
                if (args[i] == "-view") int.TryParse(args[i + 1], out view);
                if (args[i] == "-shot") shotPath = args[i + 1];
                if (args[i] == "-shotdelay") float.TryParse(args[i + 1], out shotDelay);
                if (args[i] == "-shots") int.TryParse(args[i + 1], out shotCount);
            }
            int cols = Mathf.CeilToInt(Mathf.Sqrt(areas));
            for (int i = 0; i < areas; i++)
            {
                var origin = new Vector3((i % cols) * spacing, 0f, (i / cols) * 24f);
                rooms.Add(Room.Create(i, origin, materials, seed));
            }
            var fx = gameObject.AddComponent<Effects>();
            fx.room = rooms[0];
            fx.cam = cam != null ? cam.transform : null;
            fx.particleMat = materials.particle;
        }

        void Update()
        {
            for (int k = 0; k <= 4; k++)
                if (Input.GetKeyDown(KeyCode.Alpha0 + k)) { Room.DefaultLevel = k; RestartAll(); }
            if (Input.GetKeyDown(KeyCode.R)) RestartAll();
            if (Input.GetKeyDown(KeyCode.V)) view = (view + 1) % 4;
            if (shotPath != null && Time.time > shotDelay + shotsTaken * 0.5f)
            {
                if (shotsTaken >= shotCount) { Application.Quit(); return; }
                string path = shotCount == 1 ? shotPath : shotPath.Replace(".png", $"_{shotsTaken:000}.png");
                ScreenCapture.CaptureScreenshot(path);
                shotsTaken++;
            }
        }

        void RestartAll()
        {
            foreach (var r in rooms) r.GetComponentInChildren<LaserAgent>().EndEpisode();
        }

        void LateUpdate()
        {
            if (cam == null || rooms.Count == 0) return;
            var room = rooms[0];
            var agentPos = room.transform.Find("AgentVis").position;
            Vector3 target, eye;
            switch (view)
            {
                case 1:
                    eye = agentPos + new Vector3(0, 3.4f, -4.2f);
                    target = agentPos + new Vector3(0, 0.8f, 4f);
                    break;
                case 3:     // 캐릭터 정면 클로즈업
                    eye = agentPos + new Vector3(1.2f, 1.6f, 3.2f);
                    target = agentPos + new Vector3(0, 0.9f, 0);
                    break;
                case 2:
                    eye = room.transform.position + new Vector3(13f, 6f, agentPos.z - room.transform.position.z);
                    target = agentPos + new Vector3(0, 0.6f, 0);
                    break;
                default:
                    eye = room.transform.position + new Vector3(0, 11f, -16f);
                    target = room.transform.position + new Vector3(0, 0, 1.5f);
                    break;
            }
            cam.transform.position = Vector3.Lerp(cam.transform.position, eye, 0.15f);
            cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation,
                Quaternion.LookRotation(target - cam.transform.position), 0.15f);
        }

        void OnGUI()
        {
            if (rooms.Count == 0) return;
            big ??= new GUIStyle(GUI.skin.label) { fontSize = 42, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
            small ??= new GUIStyle(GUI.skin.label) { fontSize = 18 };
            var r = rooms[0];
            GUI.Label(new Rect(16, 12, 900, 30),
                $"LEVEL {r.level}    time {r.time:0.0}s    success {r.successes}   hit {r.hits}   timeout {r.timeouts}", small);
            // Python(laser.watch)이 학습 중인 AI를 보여 줄 때 알고리즘과 학습량을 띄운다
            var p = Unity.MLAgents.Academy.Instance.EnvironmentParameters;
            int algo = Mathf.RoundToInt(p.GetWithDefault("hud_algo", 0f));
            if (algo > 0)
            {
                string[] names = { "", "PPO", "DQN", "SAC" };
                float st = p.GetWithDefault("hud_step", 0f);
                big.normal.textColor = Color.white;
                GUI.Label(new Rect(16, 36, 900, 30), $"AI: {names[Mathf.Clamp(algo, 0, 3)]}   trained {st / 1e6:0.00}M steps", small);
            }
            else
                GUI.Label(new Rect(16, 36, 900, 30),
                    "WASD move  SPACE jump  C slide  |  0-4 level  V camera  R restart  M mute", small);
            if (Time.time - r.lastResultTime < 1.0f)
            {
                var color = r.lastResult == "SUCCESS" ? new Color(0.3f, 1f, 0.4f) : new Color(1f, 0.3f, 0.3f);
                big.normal.textColor = color;
                GUI.Label(new Rect(0, Screen.height * 0.3f, Screen.width, 60), r.lastResult, big);
            }
        }
    }
}
