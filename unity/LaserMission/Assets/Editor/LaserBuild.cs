using System.IO;
using LaserMission;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.PostProcessing;

/// <summary>
/// 에디터를 손으로 만지지 않고 장면과 실행 파일을 만든다.
///   Unity.exe -batchmode -quit -projectPath unity/LaserMission -executeMethod LaserBuild.All
/// 에디터 메뉴 LaserMission에서도 실행할 수 있다.
/// </summary>
public static class LaserBuild
{
    const string ScenePath = "Assets/Scenes/Main.unity";
    const string MatDir = "Assets/Materials";

    [MenuItem("LaserMission/1. Create Scene")]
    public static void CreateScene()
    {
        Directory.CreateDirectory(MatDir);
        Directory.CreateDirectory("Assets/Scenes");
        var mats = new Room.Materials
        {
            floor = Lit("Floor", new Color(0.13f, 0.14f, 0.17f), 0.6f),
            wall = Lit("Wall", new Color(0.32f, 0.35f, 0.42f), 0.3f),
            agent = Lit("Agent", new Color(0.62f, 0.05f, 0.15f), 0.5f),      // 서강 크림슨
            visor = Lit("Visor", new Color(0.05f, 0.05f, 0.07f), 0.9f),
            vault = Lit("Vault", new Color(0.85f, 0.68f, 0.2f), 0.8f, metallic: 0.8f),
            emitter = Lit("Emitter", new Color(0.2f, 0.2f, 0.22f), 0.7f, metallic: 0.6f),
            start = Unlit("Start", new Color(0.15f, 0.35f, 0.7f)),
            goal = Unlit("Goal", new Color(0.2f, 1f, 0.4f)),
            laser = Unlit("Laser", new Color(6f, 0.35f, 0.25f)),           // 1보다 큰 값 → 블룸으로 빛난다
            laserOff = Unlit("LaserOff", new Color(0.3f, 0.05f, 0.05f)),
            glow = Additive("LaserGlow", new Color(0.6f, 0.05f, 0.03f, 0.5f)),
            strip = Unlit("Strip", new Color(0.2f, 1.6f, 2.4f)),
            particle = Particle("Particle"),
            character = MakeCharacter(),
        };
        AssetDatabase.SaveAssets();

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.42f, 0.42f, 0.48f);

        var light = new GameObject("Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 0.9f;
        light.shadows = LightShadows.Soft;
        light.shadowStrength = 0.6f;
        light.transform.rotation = Quaternion.Euler(55f, -30f, 0f);

        var cam = new GameObject("Main Camera").AddComponent<Camera>();
        cam.tag = "MainCamera";
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.03f, 0.03f, 0.05f);
        cam.fieldOfView = 50f;
        cam.transform.position = new Vector3(0, 11, -16);
        cam.transform.LookAt(new Vector3(0, 0, 1.5f));

        // 후처리: 블룸(레이저 빛 번짐), 비네트, 색 보정, 안티에일리어싱
        var layer = cam.gameObject.AddComponent<PostProcessLayer>();
        layer.Init(AssetDatabase.LoadAssetAtPath<PostProcessResources>(
            "Packages/com.unity.postprocessing/PostProcessing/PostProcessResources.asset"));
        layer.volumeLayer = ~0;
        layer.antialiasingMode = PostProcessLayer.Antialiasing.SubpixelMorphologicalAntialiasing;
        var volume = new GameObject("PostProcess").AddComponent<PostProcessVolume>();
        volume.isGlobal = true;
        volume.sharedProfile = MakeProfile();

        var boot = new GameObject("Bootstrap").AddComponent<Bootstrap>();
        boot.materials = mats;
        boot.cam = cam;

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        Debug.Log("LaserBuild: scene created");
    }

    [MenuItem("LaserMission/2. Build Windows")]
    public static void BuildWindows()
    {
        PlayerSettings.runInBackground = true;
        PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
        PlayerSettings.defaultScreenWidth = 1280;
        PlayerSettings.defaultScreenHeight = 720;
        PlayerSettings.resizableWindow = true;
        PlayerSettings.usePlayerLog = true;
        var args = System.Environment.GetCommandLineArgs();
        int pathIndex = System.Array.IndexOf(args, "-laser-build-path");
        string path = pathIndex >= 0 && pathIndex + 1 < args.Length ? args[pathIndex + 1] : "Build/LaserMission.exe";
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = path,
            target = BuildTarget.StandaloneWindows64,
            options = BuildOptions.None,
        });
        Debug.Log($"LaserBuild: build {report.summary.result}, {report.summary.totalSize / 1e6:0.0} MB");
        if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            EditorApplication.Exit(1);
    }

    public static void All()
    {
        CreateScene();
        BuildWindows();
    }

    static Material Lit(string name, Color color, float smooth, float metallic = 0f)
    {
        var m = new Material(Shader.Find("Standard")) { color = color };
        m.SetFloat("_Glossiness", smooth);
        m.SetFloat("_Metallic", metallic);
        return Save(m, name);
    }

    static Material Unlit(string name, Color color)
    {
        var m = new Material(Shader.Find("Unlit/Color")) { color = color };
        return Save(m, name);
    }

    static Material Particle(string name)
    {
        var m = new Material(Shader.Find("Legacy Shaders/Particles/Additive"));
        m.mainTexture = AssetDatabase.GetBuiltinExtraResource<Texture2D>("Default-Particle.psd");
        m.SetColor("_TintColor", new Color(0.5f, 0.5f, 0.5f, 0.5f));
        return Save(m, name);
    }

    static Material Additive(string name, Color color)
    {
        var m = new Material(Shader.Find("Legacy Shaders/Particles/Additive"));
        m.SetColor("_TintColor", color);
        return Save(m, name);
    }

    /// <summary>Assets/Characters/Albatross.obj가 있으면 텍스처 재질을 입혀 프리팹으로 만든다.</summary>
    static GameObject MakeCharacter()
    {
        var model = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Characters/Albatross.obj");
        var tex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Characters/AlbatrossTexture.png");
        if (model == null || tex == null)
        {
            Debug.Log("LaserBuild: no character model, using primitive");
            return null;
        }
        var mat = new Material(Shader.Find("Standard")) { mainTexture = tex };
        mat.SetFloat("_Glossiness", 0.25f);
        Save(mat, "Albatross");
        // 부위별 모델(Parts/)이 있으면 몸통·날개·다리를 회전 중심에 맞춰 조립한다. 없으면 통짜 모델
        var go = AssembleParts() ?? (GameObject)Object.Instantiate(model);
        foreach (var r in go.GetComponentsInChildren<Renderer>()) r.sharedMaterial = mat;
        const string path = "Assets/Characters/Albatross.prefab";
        var prefab = PrefabUtility.SaveAsPrefabAsset(go, path);
        Object.DestroyImmediate(go);
        return prefab;
    }

    [System.Serializable] class PartInfo { public float[] pivot; }
    [System.Serializable] class PartsFile { public PartInfo Body, WingL, WingR, LegL, LegR; }

    static GameObject AssembleParts()
    {
        const string dir = "Assets/Characters/Parts";
        var json = AssetDatabase.LoadAssetAtPath<TextAsset>($"{dir}/parts.json");
        if (json == null) return null;
        var info = JsonUtility.FromJson<PartsFile>(json.text);
        var root = new GameObject("Albatross");
        foreach (var (name, part) in new[] { ("Body", info.Body), ("WingL", info.WingL), ("WingR", info.WingR),
                                             ("LegL", info.LegL), ("LegR", info.LegR) })
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>($"{dir}/{name}.obj");
            if (asset == null) { Object.DestroyImmediate(root); return null; }
            var child = (GameObject)Object.Instantiate(asset, root.transform);
            child.name = name;
            // OBJ를 가져올 때 Unity가 x축을 뒤집으므로 pivot의 x도 뒤집는다
            child.transform.localPosition = new Vector3(-part.pivot[0], part.pivot[1], part.pivot[2]);
        }
        Debug.Log("LaserBuild: character assembled from parts");
        return root;
    }

    static PostProcessProfile MakeProfile()
    {
        const string path = "Assets/Materials/PostProcess.asset";
        AssetDatabase.DeleteAsset(path);
        var profile = ScriptableObject.CreateInstance<PostProcessProfile>();
        AssetDatabase.CreateAsset(profile, path);
        var bloom = profile.AddSettings<Bloom>();
        bloom.intensity.Override(2.5f);
        bloom.threshold.Override(1.1f);
        bloom.softKnee.Override(0.6f);
        var vignette = profile.AddSettings<Vignette>();
        vignette.intensity.Override(0.38f);
        var grading = profile.AddSettings<ColorGrading>();
        grading.tonemapper.Override(Tonemapper.ACES);
        grading.postExposure.Override(0.4f);
        grading.saturation.Override(8f);
        foreach (var fx in profile.settings)
        {
            fx.hideFlags = HideFlags.HideInInspector | HideFlags.HideInHierarchy;
            AssetDatabase.AddObjectToAsset(fx, profile);
        }
        AssetDatabase.SaveAssets();
        return profile;
    }

    static Material Save(Material m, string name)
    {
        string path = $"{MatDir}/{name}.mat";
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(m, path);
        return m;
    }
}
