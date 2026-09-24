using UnityEngine;
using System.Net.Sockets;
using System.Text;
using System.Globalization;

public class CameraStreamer : MonoBehaviour
{
    public TrackingMetrics trackingMetrics;

    public float panGain = 0.05f;
    public float tiltGain = 0.05f;

    public float maxPanSpeed = 2f;
    public float maxTiltSpeed = 2f;

    public Camera cam;
    public Camera externalCamera;
    public UiManager uiManager;
    public SpaceMovement spaceMovement;

    public int width = 640;
    public int height = 480;
    public int fps = 30;

    private TcpClient client;
    private NetworkStream stream;

    private RenderTexture rt;
    private Texture2D texture;

    private float timer;

    private int frameId = 0;

    // Buffer for receiving Python's response
    private byte[] receiveBuffer = new byte[1024];
    private string receiveString = "";

    // ============================================================
    // PAUSE STATE
    // ============================================================

    private bool simulationPaused = false;

    // ============================================================
    // START
    // ============================================================

    void Start()
    {
        try
        {
            client = new TcpClient(
                "127.0.0.1",
                5000
            );

            client.NoDelay = true;

            stream = client.GetStream();

            Debug.Log(
                "Connected to Python"
            );

            rt = new RenderTexture(
                width,
                height,
                24
            );

            texture = new Texture2D(
                width,
                height,
                TextureFormat.RGB24,
                false
            );
        }
        catch (System.Exception e)
        {
            Debug.LogError(
                "Connection failed: "
                + e.Message
            );
        }
    }

    // ============================================================
    // UPDATE
    // ============================================================

    void Update()
    {
        if (stream == null)
            return;

        // --------------------------------------------------------
        // IMPORTANT:
        // Receive commands BEFORE checking the timer.
        //
        // This allows RESUME to be received even when
        // Time.timeScale is currently 0.
        // --------------------------------------------------------

        ReceiveCoordinates();

        // --------------------------------------------------------
        // Send camera frame
        // --------------------------------------------------------

        timer += Time.deltaTime;

        if (timer >= 1f / fps)
        {
            timer = 0f;
            SendFrame();
        }
    }

    // ============================================================
    // SEND FRAME TO PYTHON
    // ============================================================

    void SendFrame()
    {
        if (stream == null)
            return;

        RenderTexture previous =
            cam.targetTexture;

        cam.targetTexture = rt;

        cam.Render();

        RenderTexture.active = rt;

        texture.ReadPixels(
            new Rect(
                0,
                0,
                width,
                height
            ),
            0,
            0
        );

        texture.Apply();

        cam.targetTexture = previous;

        RenderTexture.active = null;

        byte[] image =
            texture.EncodeToJPG(75);

        // --------------------------------------------------------
        // Message type
        //
        // 1 = image
        // --------------------------------------------------------

        byte[] messageType =
            new byte[] { 1 };

        // --------------------------------------------------------
        // Frame ID
        // --------------------------------------------------------

        frameId++;

        byte[] idBytes =
            System.BitConverter.GetBytes(
                frameId
            );

        // --------------------------------------------------------
        // Image size
        // --------------------------------------------------------

        byte[] sizeBytes =
            System.BitConverter.GetBytes(
                image.Length
            );

        // --------------------------------------------------------
        // Send:
        //
        // [1]
        // [4-byte frame ID]
        // [4-byte image size]
        // [JPEG]
        // --------------------------------------------------------

        stream.Write(
            messageType,
            0,
            1
        );

        stream.Write(
            idBytes,
            0,
            4
        );

        stream.Write(
            sizeBytes,
            0,
            4
        );

        stream.Write(
            image,
            0,
            image.Length
        );
    }

    // ============================================================
    // RECEIVE DATA FROM PYTHON
    // ============================================================

    void ReceiveCoordinates()
    {
        while (stream.DataAvailable)
        {
            int bytes = stream.Read(
                receiveBuffer,
                0,
                receiveBuffer.Length
            );

            if (bytes <= 0)
                return;

            receiveString +=
                Encoding.UTF8.GetString(
                    receiveBuffer,
                    0,
                    bytes
                );

            // ----------------------------------------------------
            // Process complete messages
            // ----------------------------------------------------

            while (
                receiveString.Contains("\n")
            )
            {
                int index =
                    receiveString.IndexOf(
                        "\n"
                    );

                string message =
                    receiveString
                    .Substring(
                        0,
                        index
                    )
                    .Trim();

                receiveString =
                    receiveString.Substring(
                        index + 1
                    );

                ProcessCoordinates(
                    message
                );
            }
        }
    }

    // ============================================================
    // PROCESS PYTHON MESSAGE
    // ============================================================

    void ProcessCoordinates(
        string message
    )
    {
        // ========================================================
        // PAUSE COMMAND
        // ========================================================

        if (message == "PAUSE")
        {
            PauseSimulation();
            return;
        }

        // ========================================================
        // RESUME COMMAND
        // ========================================================

        if (message == "RESUME")
        {
            ResumeSimulation();
            return;
        }

        // ========================================================
        // DISPLAY CHANGE
        // ========================================================

        if (message == "SAT_POV")
        {
            cam.targetDisplay = 0;
            externalCamera.targetDisplay = 1;

            return;
        }

        if (message == "SECOND_VIEW")
        {
            cam.targetDisplay = 1;
            externalCamera.targetDisplay = 0;

            return;
        }

        // ========================================================
        // CAMERA EFFECTS
        //
        // Message:
        // EFFECTS,noise,blur,turbulence
        // ========================================================

        if (message.StartsWith("EFFECTS,"))
        {
            string[] effectValues =
                message.Split(',');

            if (effectValues.Length != 4)
                return;

            if (
                float.TryParse(
                    effectValues[1],
                    NumberStyles.Float,
                    CultureInfo.InvariantCulture,
                    out float noise
                )
                &&
                float.TryParse(
                    effectValues[2],
                    NumberStyles.Float,
                    CultureInfo.InvariantCulture,
                    out float blur
                )
                &&
                float.TryParse(
                    effectValues[3],
                    NumberStyles.Float,
                    CultureInfo.InvariantCulture,
                    out float turbulence
                )
            )
            {
                SetEffects(
                    noise,
                    blur,
                    turbulence
                );
            }

            return;
        }

        // ========================================================
        // NORMAL COORDINATES
        // ========================================================

        string[] values =
            message.Split(',');

        if (values.Length != 4)
            return;

        if (
            float.TryParse(
                values[0],
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out float x1
            )
            &&
            float.TryParse(
                values[1],
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out float y1
            )
            &&
            float.TryParse(
                values[2],
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out float x2
            )
            &&
            float.TryParse(
                values[3],
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out float y2
            )
        )
        {
            CalculateError(
                x1,
                y1,
                x2,
                y2
            );
        }
    }

    // ============================================================
    // PAUSE SIMULATION
    // ============================================================

    void PauseSimulation()
    {
        if (simulationPaused)
            return;

        simulationPaused = true;

        Time.timeScale = 0f;

        Debug.Log(
            "=============================="
        );

        Debug.Log(
            "SIMULATION PAUSED"
        );

        Debug.Log(
            "=============================="
        );
    }

    // ============================================================
    // RESUME SIMULATION
    // ============================================================

    void ResumeSimulation()
    {
        if (!simulationPaused)
            return;

        simulationPaused = false;

        Time.timeScale = 1f;

        Debug.Log(
            "=============================="
        );

        Debug.Log(
            "SIMULATION RESUMED"
        );

        Debug.Log(
            "=============================="
        );
    }

    // ============================================================
    // CALCULATE ERROR
    // ============================================================

    void CalculateError(
        float x1,
        float y1,
        float x2,
        float y2
    )
    {
        float beaconX =
            (x1 + x2) / 2f;

        float beaconY =
            (y1 + y2) / 2f;

        float cameraX =
            width / 2f;

        float cameraY =
            height / 2f;

        float errorX =
            beaconX - cameraX;

        float errorY =
            beaconY - cameraY;

        Debug.Log(
            $"Beacon: "
            + $"({beaconX:F1}, "
            + $"{beaconY:F1}) | "
            + $"Error: "
            + $"({errorX:F1}, "
            + $"{errorY:F1})"
        );

        // --------------------------------------------------------
        // Send error to UI
        // --------------------------------------------------------

        if (trackingMetrics != null)
        {
            trackingMetrics.UpdateError(
                errorX,
                errorY
            );
        }

        // --------------------------------------------------------
        // Move camera
        // --------------------------------------------------------

        MoveCamera(
            errorX,
            errorY
        );
    }

    // ============================================================
    // MOVE CAMERA
    // ============================================================

    void MoveCamera(
        float errorX,
        float errorY
    )
    {
        // --------------------------------------------------------
        // Dead zone
        // --------------------------------------------------------

        if (Mathf.Abs(errorX) < 5f)
            errorX = 0f;

        if (Mathf.Abs(errorY) < 5f)
            errorY = 0f;

        // --------------------------------------------------------
        // Calculate movement
        // --------------------------------------------------------

        float pan =
            errorX * panGain;

        float tilt =
            -errorY * tiltGain;

        // --------------------------------------------------------
        // Limit maximum movement
        // --------------------------------------------------------

        pan = Mathf.Clamp(
            pan,
            -maxPanSpeed,
            maxPanSpeed
        );

        tilt = Mathf.Clamp(
            tilt,
            -maxTiltSpeed,
            maxTiltSpeed
        );

        // --------------------------------------------------------
        // Move camera
        // --------------------------------------------------------

        cam.transform.Rotate(
            -tilt,
            pan,
            0f,
            Space.Self
        );

        // --------------------------------------------------------
        // Send actual pan/tilt orientation
        // --------------------------------------------------------

        SendPanTilt();
    }

    // ============================================================
    // SEND PAN / TILT TO PYTHON
    //
    // Message:
    //
    // [2][PANTILT,pan,tilt\n]
    // ============================================================

    void SendPanTilt()
    {
        if (stream == null)
            return;

        Vector3 rotation =
            cam.transform.localEulerAngles;

        float pan =
            NormalizeAngle(
                rotation.y
            );

        float tilt =
            NormalizeAngle(
                rotation.x
            );

        string message =
            $"PANTILT,"
            + $"{pan.ToString("F4", CultureInfo.InvariantCulture)},"
            + $"{tilt.ToString("F4", CultureInfo.InvariantCulture)}\n";

        byte[] data =
            Encoding.UTF8.GetBytes(
                message
            );

        // --------------------------------------------------------
        // Message type 2 = Pan/Tilt
        // --------------------------------------------------------

        byte[] messageType =
            new byte[] { 2 };

        stream.Write(
            messageType,
            0,
            1
        );

        stream.Write(
            data,
            0,
            data.Length
        );
    }

    // ============================================================
    // NORMALIZE UNITY ANGLE
    //
    // Unity normally gives:
    //
    // 0 -> 360 degrees
    //
    // We convert that to:
    //
    // -180 -> +180 degrees
    // ============================================================

    float NormalizeAngle(
        float angle
    )
    {
        if (angle > 180f)
            angle -= 360f;

        return angle;
    }



    void SetEffects(
        float noise,
        float blur,
        float turbulence
    )
    {
        // --------------------------------------------------------
        // Limit values to 0 - 1
        // --------------------------------------------------------

        noise =
            Mathf.Clamp01(noise);

        blur =
            Mathf.Clamp01(blur);

        turbulence =
            Mathf.Clamp01(turbulence);

        // --------------------------------------------------------
        // Noise + Blur
        // --------------------------------------------------------

        if (uiManager != null)
        {
            uiManager.SetEffects(
                noise,
                blur
            );
        }

        // --------------------------------------------------------
        // Turbulence
        // --------------------------------------------------------

        if (spaceMovement != null)
        {
            spaceMovement.SetTurbulence(
                turbulence
            );
        }

        Debug.Log(
            $"Effects updated | " +
            $"Noise: {noise:F2} | " +
            $"Blur: {blur:F2} | " +
            $"Turbulence: {turbulence:F2}"
        );
    }



    // ============================================================
    // DESTROY
    // ============================================================

    void OnDestroy()
    {
        // Make sure time scale is restored
        Time.timeScale = 1f;

        if (stream != null)
            stream.Close();

        if (client != null)
            client.Close();

        if (rt != null)
            rt.Release();

        if (texture != null)
            Destroy(texture);
    }
}