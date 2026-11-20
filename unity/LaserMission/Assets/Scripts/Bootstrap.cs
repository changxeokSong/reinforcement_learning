using System.Collections.Generic;
using Unity.MLAgents;
using UnityEngine;

namespace LaserMission
{
    /// <summary>
    /// 실행하면 방을 만든다. 학습할 때는 Python이 "-areas 16"처럼 방 개수를 넘겨서
    /// 한 프로세스 안에서 여러 판을 동시에 진행한다. 화면에는 0번 방이 보인다.
    ///
    /// 독립 실행은 10단계 캠페인으로 시작한다. Python 연결과 -level 실행은 개별 레벨을 사용한다.
    /// </summary>
    public class Bootstrap : MonoBehaviour
    {
        public Room.Materials materials;
        public Camera cam;
        public int areas = 1;
        public float spacing = 12f;

        readonly List<Room> rooms = new List<Room>();
        static readonly string[] ViewNames = { "Overview", "Chase", "Side", "Front" };
        int view;
        float cameraFieldOfView, defaultFieldOfView;
        float orbitYaw, orbitPitch;
        GUIStyle big, small;
        string shotPath;                // -shot 경로: 화면을 찍고 종료한다 (보고서·확인용)
        float shotDelay = 4f;
        int shotCount = 1, shotsTaken;
        string recordDir;               // -record 폴더: 매 프레임을 PNG로 저장한다 (GIF 녹화용, 30fps)
        bool recordOffscreen;
        RenderTexture recordTarget;
        Texture2D recordPixels;
        int recordFrame;
        bool localPlay;
        CampaignProgress campaign;

        void Awake()
        {
            // 결정 한 번이 게임 시간 0.1초다. 시간 배속 1이면 실제 시간과 같은 속도로 보인다
            Time.fixedDeltaTime = 0.1f;
            Application.targetFrameRate = 60;
            int seed = 0;
            int? campaignSeed = null;
            var args = System.Environment.GetCommandLineArgs();
            bool practice = System.Array.IndexOf(args, "-practice") >= 0;
            recordOffscreen = System.Array.IndexOf(args, "-record-offscreen") >= 0;
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "-areas") int.TryParse(args[i + 1], out areas);
                if (args[i] == "-envseed" && int.TryParse(args[i + 1], out int requestedSeed))
                {
                    seed = requestedSeed;
                    campaignSeed = requestedSeed;
                }
                if (args[i] == "-level" && int.TryParse(args[i + 1], out int lv))
                {
                    Room.DefaultLevel = lv;
                    practice = true;
                }
                if (args[i] == "-view" && int.TryParse(args[i + 1], out int startView))
                    SelectView(startView);
                if (args[i] == "-shot") shotPath = args[i + 1];
                if (args[i] == "-shotdelay") float.TryParse(args[i + 1], out shotDelay);
                if (args[i] == "-shots") int.TryParse(args[i + 1], out shotCount);
                if (args[i] == "-record") recordDir = args[i + 1];
            }
            localPlay = !Application.isBatchMode && !Academy.Instance.IsCommunicatorOn;
            if (localPlay && areas == 1) campaign = new CampaignProgress(campaignSeed);
            int cols = Mathf.CeilToInt(Mathf.Sqrt(areas));
            for (int i = 0; i < areas; i++)
            {
                var origin = new Vector3((i % cols) * spacing, 0f, (i / cols) * 24f);
                rooms.Add(Room.Create(i, origin, materials, seed, practice ? null : campaign));
            }
            var fx = gameObject.AddComponent<Effects>();
            fx.room = rooms[0];
            fx.cam = cam != null ? cam.transform : null;
            fx.particleMat = materials.particle;
            if (cam != null) cameraFieldOfView = defaultFieldOfView = cam.fieldOfView;
        }

        void Update()
        {
            if (localPlay) UpdateLocalPlay();
            if (Input.GetKeyDown(KeyCode.V)) SelectView((view + 1) % ViewNames.Length);
            for (int k = 0; k < ViewNames.Length; k++)
                if (Input.GetKeyDown(KeyCode.F1 + k)) SelectView(k);
            if (Input.GetKeyDown(KeyCode.Home))
            {
                SelectView(view);
                cameraFieldOfView = defaultFieldOfView;
            }
            if (cam != null)
            {
                cameraFieldOfView = Mathf.Clamp(cameraFieldOfView - 5f * Input.mouseScrollDelta.y, 25f, 80f);
                if (Input.GetMouseButton(1))
                {
                    orbitYaw = Mathf.Repeat(orbitYaw + 3f * Input.GetAxisRaw("Mouse X"), 360f);
                    orbitPitch = Mathf.Clamp(orbitPitch - 2f * Input.GetAxisRaw("Mouse Y"), -25f, 35f);
                }
            }
            if (shotPath != null && Time.time > shotDelay + shotsTaken * 0.5f)
            {
                if (shotsTaken >= shotCount) { Application.Quit(); return; }
                string path = shotCount == 1 ? shotPath : shotPath.Replace(".png", $"_{shotsTaken:000}.png");
                ScreenCapture.CaptureScreenshot(path);
                shotsTaken++;
            }
        }

        void UpdateLocalPlay()
        {
            var room = rooms[0];
            if (campaign != null && Input.GetKeyDown(KeyCode.P))
            {
                room.Campaign = room.Campaign == null ? campaign : null;
                room.ResetEpisode();
                return;
            }

            if (room.Campaign != null)
            {
                var phase = campaign.CurrentPhase;
                bool advance = Input.GetKeyDown(KeyCode.Return) && phase != CampaignProgress.Phase.Playing;
                bool retry = Input.GetKeyDown(KeyCode.R) &&
                    (phase == CampaignProgress.Phase.Playing || phase == CampaignProgress.Phase.Retry);
                if (advance || retry)
                {
                    campaign.Continue();
                    room.ResetEpisode();
                }
                return;
            }

            for (int k = 0; k <= 9; k++)
            {
                if (!Input.GetKeyDown(KeyCode.Alpha0 + k)) continue;
                Room.DefaultLevel = k;
                RestartAll();
                return;
            }
            if (Input.GetKeyDown(KeyCode.Equals))
            {
                Room.DefaultLevel = Room.MaxLevel;
                RestartAll();
            }
            else if (Input.GetKeyDown(KeyCode.R))
                RestartAll();
        }

        void SelectView(int index)
        {
            view = Mathf.Clamp(index, 0, ViewNames.Length - 1);
            orbitYaw = orbitPitch = 0f;
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
            var offset = Quaternion.AngleAxis(orbitYaw, Vector3.up) * (eye - target);
            var pitchAxis = Vector3.Cross(Vector3.up, offset).normalized;
            eye = target + Quaternion.AngleAxis(orbitPitch, pitchAxis) * offset;
            cam.transform.position = Vector3.Lerp(cam.transform.position, eye, 0.15f);
            cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation,
                Quaternion.LookRotation(target - cam.transform.position), 0.15f);
            cam.fieldOfView = Mathf.Lerp(cam.fieldOfView, cameraFieldOfView, 0.2f);
            if (recordDir != null) CaptureFrame();
        }

        void CaptureFrame()
        {
            Time.captureFramerate = 30;
            string file = System.IO.Path.Combine(recordDir, $"frame_{recordFrame++:00000}.png");
            if (!recordOffscreen)
            {
                ScreenCapture.CaptureScreenshot(file);
                return;
            }

            if (recordTarget == null)
            {
                recordTarget = new RenderTexture(1280, 720, 24, RenderTextureFormat.ARGB32);
                recordPixels = new Texture2D(recordTarget.width, recordTarget.height, TextureFormat.RGB24, false);
            }
            var priorTarget = cam.targetTexture;
            var priorActive = RenderTexture.active;
            try
            {
                cam.targetTexture = recordTarget;
                cam.Render();
                RenderTexture.active = recordTarget;
                recordPixels.ReadPixels(new Rect(0, 0, recordTarget.width, recordTarget.height), 0, 0, false);
                System.IO.File.WriteAllBytes(file, recordPixels.EncodeToPNG());
            }
            finally
            {
                cam.targetTexture = priorTarget;
                RenderTexture.active = priorActive;
            }
        }

        void OnDestroy()
        {
            if (recordTarget != null) Destroy(recordTarget);
            if (recordPixels != null) Destroy(recordPixels);
        }

        void OnGUI()
        {
            if (rooms.Count == 0) return;
            big ??= new GUIStyle(GUI.skin.label) { fontSize = 42, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
            small ??= new GUIStyle(GUI.skin.label) { fontSize = 18 };
            var r = rooms[0];
            string levelLabel = r.Campaign != null
                ? $"STAGE {r.level}/{Room.MaxLevel}    Layout {r.Campaign.LayoutSeed}"
                : $"LEVEL {r.level}";
            GUI.Label(new Rect(16, 12, 900, 30),
                $"{levelLabel}    time {r.time:0.0}s    success {r.successes}   hit {r.hits}   timeout {r.timeouts}", small);
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
            else if (localPlay)
            {
                string keys = r.Campaign != null ? "P practice" : "0-9, = select level   P campaign";
                GUI.Label(new Rect(16, 36, 1100, 30),
                    $"WASD move   SPACE jump   C slide   R retry   M mute   |   {keys}", small);
            }
            GUI.Label(new Rect(16, 60, 1100, 30),
                $"Camera: {ViewNames[view]}   V / F1-F4 switch   Right-drag orbit   Wheel zoom   Home reset", small);
            if (r.Campaign != null && r.Campaign.CurrentPhase != CampaignProgress.Phase.Playing)
                DrawCampaignResult(r.Campaign);
            else if (Time.time - r.lastResultTime < 1.0f)
            {
                var color = r.lastResult == "SUCCESS" ? new Color(0.3f, 1f, 0.4f) : new Color(1f, 0.3f, 0.3f);
                big.normal.textColor = color;
                GUI.Label(new Rect(0, Screen.height * 0.3f, Screen.width, 60), r.lastResult, big);
            }
        }

        void DrawCampaignResult(CampaignProgress progress)
        {
            float width = Mathf.Min(560f, Screen.width - 24f);
            var panel = new Rect((Screen.width - width) * 0.5f, Screen.height * 0.33f, width, 122f);
            GUI.Box(panel, GUIContent.none);
            string title, prompt;
            switch (progress.CurrentPhase)
            {
                case CampaignProgress.Phase.Complete:
                    title = "MISSION COMPLETE";
                    prompt = $"All {Room.MaxLevel} stages cleared. Press Enter to start a new run.";
                    break;
                case CampaignProgress.Phase.StageCleared:
                    title = $"STAGE {progress.Stage} CLEAR";
                    prompt = "Press Enter for the next stage.";
                    break;
                default:
                    title = rooms[0].lastResult;
                    prompt = "Press Enter or R to retry this stage with a new layout.";
                    break;
            }
            big.normal.textColor = Color.white;
            GUI.Label(new Rect(panel.x, panel.y + 10f, panel.width, 58f), title, big);
            var promptStyle = new GUIStyle(small) { alignment = TextAnchor.MiddleCenter };
            GUI.Label(new Rect(panel.x, panel.y + 71f, panel.width, 36f), prompt, promptStyle);
        }
    }
}
