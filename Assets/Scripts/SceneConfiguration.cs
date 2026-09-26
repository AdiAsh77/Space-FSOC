using UnityEngine;

public class SceneConfiguration : MonoBehaviour
{
    // ============================================================
    // SCENE OBJECTS
    // ============================================================

    public GameObject beacon;
    public GameObject satellite;

    public SpaceMovement spaceMovement;
    public BeaconMovement beaconMovement;

    public UiManager uiManager;


    // ============================================================
    // APPLY SCENE JSON
    // ============================================================

    public void ApplyScene(string json)
    {
        Debug.Log("================================");
        Debug.Log("APPLYING SCENE CONFIGURATION");
        Debug.Log(json);
        Debug.Log("================================");


        SceneData scene;

        try
        {
            scene =
                JsonUtility.FromJson<SceneData>(json);
        }
        catch (System.Exception e)
        {
            Debug.LogError(
                "Failed to parse scene JSON: "
                + e.Message
            );

            return;
        }


        // ========================================================
        // BEACON
        // ========================================================

        if (scene.beacon != null)
        {
            ApplyBeaconSettings(
                scene.beacon
            );
        }


        // ========================================================
        // SATELLITE
        // ========================================================

        if (scene.satellite != null)
        {
            ApplySatelliteSettings(
                scene.satellite
            );
        }


        // ========================================================
        // DISTURBANCES
        // ========================================================

        if (scene.disturbances != null)
        {
            ApplyDisturbanceSettings(
                scene.disturbances
            );
        }


        Debug.Log(
            "SCENE CONFIGURATION APPLIED"
        );
    }


    // ============================================================
    // BEACON SETTINGS
    // ============================================================

    void ApplyBeaconSettings(
        BeaconSettings settings
    )
    {
        // --------------------------------------------------------
        // Start Position
        // --------------------------------------------------------

        if (beacon != null)
        {
            if (
                settings.start_position
                == "Out of Pov"
            )
            {
                MoveBeaconOutOfView();
            }
        }


        // --------------------------------------------------------
        // Movement Type
        // --------------------------------------------------------

        if (beaconMovement != null)
        {
            beaconMovement.SetMovementType(
                settings.movement_type
            );
        }


        Debug.Log(
            "Beacon | "
            + "Start Position: "
            + settings.start_position
            + " | Movement: "
            + settings.movement_type
        );
    }


    // ============================================================
    // SATELLITE SETTINGS
    // ============================================================

    void ApplySatelliteSettings(
        SatelliteSettings settings
    )
    {
        // --------------------------------------------------------
        // Satellite Position
        // --------------------------------------------------------

        if (
            satellite != null
            &&
            settings.satellite_position == "Random"
        )
        {
            SetRandomSatellitePosition();
        }


        // --------------------------------------------------------
        // Satellite Rotation
        // --------------------------------------------------------

        if (
            satellite != null
            &&
            settings.satellite_rotation == "Random"
        )
        {
            SetRandomSatelliteRotation();
        }


        Debug.Log(
            "Satellite | "
            + "Distance: "
            + settings.distance_from_beacon
            + " | Position: "
            + settings.satellite_position
            + " | Rotation: "
            + settings.satellite_rotation
        );
    }


    // ============================================================
    // DISTURBANCE SETTINGS
    // ============================================================

    void ApplyDisturbanceSettings(
        DisturbanceSettings settings
    )
    {
        // --------------------------------------------------------
        // Noise
        // --------------------------------------------------------

        float noise =
            Mathf.Clamp01(
                settings.noise_level
            );


        // --------------------------------------------------------
        // Blur
        // --------------------------------------------------------

        float blur =
            Mathf.Clamp01(
                settings.blur_level
            );


        // --------------------------------------------------------
        // Atmospheric disturbance
        //
        // This is turbulence.
        // --------------------------------------------------------

        float turbulence =
            Mathf.Clamp01(
                settings.atmospheric_disturbance
            );


        // --------------------------------------------------------
        // Apply Noise + Blur
        // --------------------------------------------------------

        if (uiManager != null)
        {
            uiManager.SetEffects(
                noise,
                blur
            );
        }


        // --------------------------------------------------------
        // Apply Turbulence
        // --------------------------------------------------------

        if (spaceMovement != null)
        {
            spaceMovement.SetTurbulence(
                turbulence
            );
        }


        Debug.Log(
            "Disturbances | "
            + "Noise: "
            + noise
            + " | Blur: "
            + blur
            + " | Turbulence: "
            + turbulence
        );
    }


    // ============================================================
    // BEACON OUT OF VIEW
    // ============================================================

    void MoveBeaconOutOfView()
    {
        if (beacon == null)
            return;

        Camera mainCamera =
            Camera.main;

        if (mainCamera == null)
            return;


        // Put beacon behind the camera.
        Vector3 position =
            mainCamera.transform.position
            -
            mainCamera.transform.forward * 20f;

        beacon.transform.position =
            position;


        Debug.Log(
            "Beacon moved OUT OF POV"
        );
    }


    // ============================================================
    // RANDOM SATELLITE POSITION
    // ============================================================

    void SetRandomSatellitePosition()
    {
        if (satellite == null)
            return;

        satellite.transform.position =
            new Vector3(
                Random.Range(-20f, 20f),
                Random.Range(-10f, 10f),
                Random.Range(20f, 50f)
            );


        Debug.Log(
            "Satellite position randomized"
        );
    }


    // ============================================================
    // RANDOM SATELLITE ROTATION
    // ============================================================

    void SetRandomSatelliteRotation()
    {
        if (satellite == null)
            return;

        satellite.transform.rotation =
            Quaternion.Euler(
                Random.Range(0f, 360f),
                Random.Range(0f, 360f),
                Random.Range(0f, 360f)
            );


        Debug.Log(
            "Satellite rotation randomized"
        );
    }
}


// =================================================================
// JSON DATA CLASSES
// =================================================================

[System.Serializable]
public class SceneData
{
    public BeaconSettings beacon;
    public SatelliteSettings satellite;
    public DisturbanceSettings disturbances;
}


[System.Serializable]
public class BeaconSettings
{
    public string start_position;
    public string movement_type;
}


[System.Serializable]
public class SatelliteSettings
{
    public float distance_from_beacon;
    public string satellite_position;
    public string satellite_rotation;
}


[System.Serializable]
public class DisturbanceSettings
{
    public float noise_level;
    public float blur_level;
    public float atmospheric_disturbance;
}