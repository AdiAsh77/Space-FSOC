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

    // Tracking Camera / Main Camera
    public Camera trackingCamera;


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
            scene = JsonUtility.FromJson<SceneData>(json);
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
        // SATELLITE FIRST
        // ========================================================

        if (scene.satellite != null)
        {
            ApplySatelliteSettings(
                scene.satellite
            );
        }


        // ========================================================
        // BEACON SECOND
        // ========================================================

        if (scene.beacon != null)
        {
            ApplyBeaconSettings(
                scene.beacon
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

    void ApplyBeaconSettings(BeaconSettings settings)
    {
        string startPosition = settings.start_position;
        if (beacon != null)
        {


            // ----------------------------------------------------
            // RANDOM
            // ----------------------------------------------------

            if (startPosition == "Random")
            {
                string[] positions =
                {
                    "Out of Fov",
                    "Center",
                    "Top-Left",
                    "Top-Right",
                    "Bottom-Left",
                    "Bottom-Right"
                };

                int randomIndex =
                    Random.Range(
                        0,
                        positions.Length
                    );

                startPosition =
                    positions[randomIndex];

                Debug.Log(
                    "Random start position selected: "
                    + startPosition
                );
            }


            // ----------------------------------------------------
            // POSITION BEACON
            // ----------------------------------------------------

            if (startPosition == "Out of Fov")
            {
                MoveBeaconOutOfView();
            }
            else if (startPosition == "Center")
            {
                MoveBeaconToFovPosition(
                    0.5f,
                    0.5f
                );
            }
            else if (startPosition == "Top-Left")
            {
                MoveBeaconToRandomFovArea(
                    0f,
                    0.5f,
                    0.5f,
                    1f
                );
            }
            else if (startPosition == "Top-Right")
            {
                MoveBeaconToRandomFovArea(
                    0.5f,
                    1f,
                    0.5f,
                    1f
                );
            }
            else if (startPosition == "Bottom-Left")
            {
                MoveBeaconToRandomFovArea(
                    0f,
                    0.5f,
                    0f,
                    0.5f
                );
            }
            else if (startPosition == "Bottom-Right")
            {
                MoveBeaconToRandomFovArea(
                    0.5f,
                    1f,
                    0f,
                    0.5f
                );
            }
            else
            {
                Debug.LogWarning(
                    "Unknown beacon start position: "
                    + startPosition
                );
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
            + startPosition
            + " | Movement: "
            + settings.movement_type
        );
    }


    // ============================================================
    // MOVE BEACON TO FOV POSITION
    //
    // viewportX:
    // 0 = left
    // 1 = right
    //
    // viewportY:
    // 0 = bottom
    // 1 = top
    // ============================================================

    void MoveBeaconToFovPosition(
        float viewportX,
        float viewportY
    )
    {
        if (beacon == null)
            return;

        if (trackingCamera == null)
        {
            trackingCamera =
                Camera.main;
        }

        if (trackingCamera == null)
        {
            Debug.LogError(
                "Tracking Camera not assigned!"
            );

            return;
        }


        // --------------------------------------------------------
        // Distance from camera
        // --------------------------------------------------------

        float distance =
            GetBeaconDistance();


        // --------------------------------------------------------
        // Convert viewport position to world position
        // --------------------------------------------------------

        Vector3 viewportPosition =
            new Vector3(
                viewportX,
                viewportY,
                distance
            );

        Vector3 worldPosition =
            trackingCamera.ViewportToWorldPoint(
                viewportPosition
            );


        beacon.transform.position =
            worldPosition;


        Debug.Log(
            "Beacon moved to FOV position | "
            + "Viewport: ("
            + viewportX
            + ", "
            + viewportY
            + ")"
        );
    }


    // ============================================================
    // MOVE BEACON TO RANDOM FOV AREA
    // ============================================================

    void MoveBeaconToRandomFovArea(
        float minX,
        float maxX,
        float minY,
        float maxY
    )
    {
        float viewportX =
            Random.Range(
                minX,
                maxX
            );

        float viewportY =
            Random.Range(
                minY,
                maxY
            );


        MoveBeaconToFovPosition(
            viewportX,
            viewportY
        );
    }


    // ============================================================
    // BEACON DISTANCE
    // ============================================================

    float GetBeaconDistance()
    {
        if (trackingCamera == null)
        {
            trackingCamera =
                Camera.main;
        }

        if (trackingCamera == null)
            return 20f;


        // --------------------------------------------------------
        // Try to preserve the beacon's current distance from
        // the camera.
        // --------------------------------------------------------

        float distance =
            Vector3.Distance(
                trackingCamera.transform.position,
                beacon.transform.position
            );


        // --------------------------------------------------------
        // Prevent an invalid or extremely small distance.
        // --------------------------------------------------------

        if (distance < 1f)
        {
            distance = 20f;
        }


        return distance;
    }


    // ============================================================
    // BEACON OUT OF VIEW
    // ============================================================

    void MoveBeaconOutOfView()
    {
        if (beacon == null)
            return;

        if (trackingCamera == null)
        {
            trackingCamera =
                Camera.main;
        }

        if (trackingCamera == null)
        {
            Debug.LogError(
                "Tracking Camera not assigned!"
            );

            return;
        }


        // --------------------------------------------------------
        // Put beacon behind the camera.
        // --------------------------------------------------------

        Vector3 position =
            trackingCamera.transform.position
            -
            trackingCamera.transform.forward
            * 20f;


        beacon.transform.position =
            position;


        Debug.Log(
            "Beacon moved OUT OF FOV"
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