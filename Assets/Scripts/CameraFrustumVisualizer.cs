using UnityEngine;

public class CameraFrustumVisualizer : MonoBehaviour
{
    public Camera targetCamera;

    // ============================================================
    // FRUSTUM APPEARANCE
    // ============================================================

    public Material frustumMaterial;
    public float lineWidth = 0.01f;

    // Controls how wide the visualized FOV is.
    // 1.0 = actual camera FOV
    // 0.5 = half the visualized width/height
    public float frustumWidth = 0.5f;

    public float frustumLength = 5f;

    public Color frustumColor = Color.white;

    private LineRenderer[] lines;

    void Start()
    {
        if (targetCamera == null)
            targetCamera = GetComponent<Camera>();

        CreateFrustum();
    }

    void LateUpdate()
    {
        UpdateFrustum();

        // UpdateVisibility();
    }

    // ============================================================
    // CREATE FRUSTUM
    // ============================================================

    void CreateFrustum()
    {
        lines = new LineRenderer[8];

        for (int i = 0; i < lines.Length; i++)
        {
            GameObject lineObject =
                new GameObject("FrustumLine_" + i);

            lineObject.transform.SetParent(
                transform,
                false
            );

            lineObject.layer =
                LayerMask.NameToLayer(
                    "FrustumVisualization"
                );

            LineRenderer line =
                lineObject.AddComponent<LineRenderer>();

            line.positionCount = 2;

            line.startWidth = lineWidth;
            line.endWidth = lineWidth;

            line.useWorldSpace = true;

            // --------------------------------------------------------
            // Use assigned URP material
            // --------------------------------------------------------

            if (frustumMaterial != null)
            {
                line.material = frustumMaterial;
            }
            else
            {
                Debug.LogError(
                    "Frustum Material is not assigned!"
                );
            }

            // --------------------------------------------------------
            // Set colour
            // --------------------------------------------------------

            line.startColor = frustumColor;
            line.endColor = frustumColor;

            lines[i] = line;
        }
    }

    // ============================================================
    // UPDATE FRUSTUM
    // ============================================================

    void UpdateFrustum()
    {
        if (targetCamera == null)
            return;

        Vector3[] corners =
            new Vector3[4];

        // --------------------------------------------------------
        // Calculate actual camera FOV size
        // --------------------------------------------------------

        float height =
            2f *
            Mathf.Tan(
                targetCamera.fieldOfView * 0.5f *
                Mathf.Deg2Rad
            ) *
            frustumLength;

        float width =
            height *
            targetCamera.aspect;

        // --------------------------------------------------------
        // Make the visualized FOV narrower
        //
        // This DOES NOT change the real camera FOV.
        // --------------------------------------------------------

        width *= frustumWidth;
        height *= frustumWidth;

        Vector3 center =
            targetCamera.transform.position +
            targetCamera.transform.forward *
            frustumLength;

        Vector3 right =
            targetCamera.transform.right *
            width *
            0.5f;

        Vector3 up =
            targetCamera.transform.up *
            height *
            0.5f;

        // --------------------------------------------------------
        // Four corners
        // --------------------------------------------------------

        corners[0] =
            center - right - up;

        corners[1] =
            center + right - up;

        corners[2] =
            center + right + up;

        corners[3] =
            center - right + up;

        Vector3 cameraPosition =
            targetCamera.transform.position;

        // --------------------------------------------------------
        // Camera -> far corners
        // --------------------------------------------------------

        SetLine(
            lines[0],
            cameraPosition,
            corners[0]
        );

        SetLine(
            lines[1],
            cameraPosition,
            corners[1]
        );

        SetLine(
            lines[2],
            cameraPosition,
            corners[2]
        );

        SetLine(
            lines[3],
            cameraPosition,
            corners[3]
        );

        // --------------------------------------------------------
        // Far rectangle
        // --------------------------------------------------------

        SetLine(
            lines[4],
            corners[0],
            corners[1]
        );

        SetLine(
            lines[5],
            corners[1],
            corners[2]
        );

        SetLine(
            lines[6],
            corners[2],
            corners[3]
        );

        SetLine(
            lines[7],
            corners[3],
            corners[0]
        );
    }

    // ============================================================
    // UPDATE VISIBILITY
    // ============================================================

    void UpdateVisibility()
    {
        if (targetCamera == null)
            return;

        // --------------------------------------------------------
        // If the Tracking Camera is currently being viewed,
        // hide the frustum.
        //
        // If another camera (External Camera) is viewing the
        // scene, show the frustum.
        // --------------------------------------------------------

        bool trackingCameraIsActive =
            targetCamera.enabled &&
            targetCamera.gameObject.activeInHierarchy;

        bool externalView =
            Camera.main != targetCamera;

        bool shouldShow =
            externalView;

        for (int i = 0; i < lines.Length; i++)
        {
            lines[i].enabled = shouldShow;
        }
    }

    // ============================================================
    // SET LINE
    // ============================================================

    void SetLine(
        LineRenderer line,
        Vector3 start,
        Vector3 end
    )
    {
        line.SetPosition(0, start);
        line.SetPosition(1, end);
    }
}