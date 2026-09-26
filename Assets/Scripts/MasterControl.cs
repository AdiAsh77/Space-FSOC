using UnityEngine;
using UnityEngine.InputSystem;

public class MasterControl : MonoBehaviour
{
    [Header("Simulation Objects")]
    public GameObject[] simulationObjects;

    [Header("Video Objects")]
    public GameObject[] videoObjects;

    [Header("Simulation Scripts")]
    public MonoBehaviour[] simulationScripts;

    [Header("Video Scripts")]
    public MonoBehaviour[] videoScripts;

    private bool simulationMode = true;

    void Start()
    {
        SwitchToSimulation();
    }

    void Update()
    {
        if (Keyboard.current == null)
            return;

        // 1 = Simulation Mode
        if (Keyboard.current.digit1Key.wasPressedThisFrame)
        {
            SwitchToSimulation();
        }

        // 2 = Video Mode
        if (Keyboard.current.digit2Key.wasPressedThisFrame)
        {
            SwitchToVideo();
        }

        // O = Pause Simulation
        if (Keyboard.current.oKey.wasPressedThisFrame)
        {
            Pause1();
        }

        // P = Resume Simulation
        if (Keyboard.current.pKey.wasPressedThisFrame)
        {
            Resume1();
        }

        // T = Pause Video
        if (Keyboard.current.tKey.wasPressedThisFrame)
        {
            Pause2();
        }

        // Y = Resume Video
        if (Keyboard.current.yKey.wasPressedThisFrame)
        {
            Resume2();
        }
    }

    // =========================
    // SIMULATION
    // =========================

    public void Pause1()
    {
        SetScriptsActive(simulationScripts, false);

        Debug.Log("Simulation PAUSED");
    }

    public void Resume1()
    {
        SetScriptsActive(simulationScripts, true);

        Debug.Log("Simulation RESUMED");
    }

    // =========================
    // VIDEO / GIMBAL
    // =========================

    public void Pause2()
    {
        SetScriptsActive(videoScripts, false);

        Debug.Log("Video/Gimbal PAUSED");
    }

    public void Resume2()
    {
        SetScriptsActive(videoScripts, true);

        Debug.Log("Video/Gimbal RESUMED");
    }

    // =========================
    // MODE SWITCHING
    // =========================

    public void SwitchToSimulation()
    {
        simulationMode = true;

        // Stop video movement/control
        Pause2();

        // Disable video objects
        SetObjectsActive(videoObjects, false);

        // Enable simulation objects
        SetObjectsActive(simulationObjects, true);

        // Start simulation movement/control
        Resume1();

        Debug.Log("==============================");
        Debug.Log("MODE: SIMULATION");
        Debug.Log("==============================");
    }

    public void SwitchToVideo()
    {
        simulationMode = false;

        // Stop simulation movement/control
        Pause1();

        // Disable simulation objects
        SetObjectsActive(simulationObjects, false);

        // Enable video objects
        SetObjectsActive(videoObjects, true);

        // Start video/gimbal movement/control
        Resume2();

        Debug.Log("==============================");
        Debug.Log("MODE: VIDEO");
        Debug.Log("==============================");
    }

    // =========================
    // HELPERS
    // =========================

    void SetObjectsActive(GameObject[] objects, bool active)
    {
        if (objects == null)
            return;

        foreach (GameObject obj in objects)
        {
            if (obj != null)
            {
                obj.SetActive(active);
            }
        }
    }

    void SetScriptsActive(MonoBehaviour[] scripts, bool active)
    {
        if (scripts == null)
            return;

        foreach (MonoBehaviour script in scripts)
        {
            if (script != null)
            {
                script.enabled = active;
            }
        }
    }
}