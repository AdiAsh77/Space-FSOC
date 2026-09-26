using UnityEngine;

public class SearchPattern : MonoBehaviour
{
    [Header("Camera")]
    public Camera targetCamera;

    [Header("Pan")]
    public float panSpeed = 30f;

    [Header("Tilt")]
    public float minTilt = -60f;
    public float maxTilt = 60f;
    public float tiltStep = 20f;

    private bool searching = false;

    private float panAngle = 0f;
    private float tiltAngle = 0f;

    private int panDirection = 1;
    private int tiltDirection = 1;

    void Update()
    {
        if (!searching)
            return;

        PerformSearch();
    }

    public void StartSearch()
    {
        if (targetCamera == null)
        {
            Debug.LogError("SearchPattern: Target Camera is not assigned.");
            return;
        }

        if (searching)
            return;

        searching = true;

        // Start from the camera's current orientation
        Vector3 rotation =
            targetCamera.transform.localEulerAngles;

        panAngle = NormalizeAngle(rotation.y);
        tiltAngle = NormalizeAngle(rotation.x);

        // Start sweeping horizontally
        panDirection = 1;

        Debug.Log("==============================");
        Debug.Log("SEARCH STARTED");
        Debug.Log("==============================");
    }

    public void StopSearch()
    {
        if (!searching)
            return;

        searching = false;

        Debug.Log("==============================");
        Debug.Log("SEARCH STOPPED");
        Debug.Log("==============================");
    }

    void PerformSearch()
    {
        // ----------------------------------------------------
        // Move horizontally
        // ----------------------------------------------------

        panAngle +=
            panDirection *
            panSpeed *
            Time.deltaTime;

        // ----------------------------------------------------
        // Reached right side
        // ----------------------------------------------------

        if (panDirection > 0 && panAngle >= 180f)
        {
            panAngle = 180f;

            MoveTilt();

            panDirection = -1;
        }

        // ----------------------------------------------------
        // Reached left side
        // ----------------------------------------------------

        else if (panDirection < 0 && panAngle <= -180f)
        {
            panAngle = -180f;

            MoveTilt();

            panDirection = 1;
        }

        // ----------------------------------------------------
        // Apply camera rotation
        // ----------------------------------------------------

        targetCamera.transform.localRotation =
            Quaternion.Euler(
                -tiltAngle,
                panAngle,
                0f
            );
    }

    void MoveTilt()
    {
        tiltAngle +=
            tiltDirection *
            tiltStep;

        // ----------------------------------------------------
        // Reached upper limit
        // ----------------------------------------------------

        if (tiltAngle >= maxTilt)
        {
            tiltAngle = maxTilt;
            tiltDirection = -1;
        }

        // ----------------------------------------------------
        // Reached lower limit
        // ----------------------------------------------------

        else if (tiltAngle <= minTilt)
        {
            tiltAngle = minTilt;
            tiltDirection = 1;
        }
    }

    float NormalizeAngle(float angle)
    {
        if (angle > 180f)
            angle -= 360f;

        return angle;
    }
}