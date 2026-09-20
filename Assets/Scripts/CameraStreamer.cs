using UnityEngine;
using System.Net.Sockets;
using System.Text;

public class CameraStreamer : MonoBehaviour
{
    public TrackingMetrics trackingMetrics;

    public float panGain = 0.05f;
    public float tiltGain = 0.05f;

    public float maxPanSpeed = 2f;
    public float maxTiltSpeed = 2f;

    public Camera cam;

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

    void Start()
    {
        try
        {
            client = new TcpClient("127.0.0.1", 5000);
            client.NoDelay = true;

            stream = client.GetStream();

            Debug.Log("Connected to Python");

            rt = new RenderTexture(width, height, 24);

            texture = new Texture2D(
                width,
                height,
                TextureFormat.RGB24,
                false
            );
        }
        catch (System.Exception e)
        {
            Debug.LogError("Connection failed: " + e.Message);
        }
    }

    void Update()
    {
        if (stream == null)
            return;

        ReceiveCoordinates();

        timer += Time.deltaTime;

        if (timer >= 1f / fps)
        {
            timer = 0f;
            SendFrame();
        }
    }

    void SendFrame()
    {
        RenderTexture previous = cam.targetTexture;

        cam.targetTexture = rt;
        cam.Render();

        RenderTexture.active = rt;

        texture.ReadPixels(
            new Rect(0, 0, width, height),
            0,
            0
        );

        texture.Apply();

        cam.targetTexture = previous;
        RenderTexture.active = null;

        byte[] image = texture.EncodeToJPG(75);

        // Send image length first
        frameId++;

        byte[] idBytes = System.BitConverter.GetBytes(frameId);
        byte[] sizeBytes = System.BitConverter.GetBytes(image.Length);

        // Message type 1 = image frame
        byte[] messageType = new byte[] { 1 };

        stream.Write(messageType, 0, 1);

        // Frame ID
        stream.Write(idBytes, 0, 4);

        // Image size
        stream.Write(sizeBytes, 0, 4);

        // JPEG
        stream.Write(image, 0, image.Length);
    }

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

            receiveString += Encoding.UTF8.GetString(
                receiveBuffer,
                0,
                bytes
            );

            // Process complete messages
            while (receiveString.Contains("\n"))
            {
                int index = receiveString.IndexOf("\n");

                string message = receiveString
                    .Substring(0, index)
                    .Trim();

                receiveString = receiveString
                    .Substring(index + 1);

                ProcessCoordinates(message);
            }
        }
    }

    void ProcessCoordinates(string message)
    {
        string[] values = message.Split(',');

        if (values.Length != 4)
            return;

        if (
            float.TryParse(values[0], out float x1) &&
            float.TryParse(values[1], out float y1) &&
            float.TryParse(values[2], out float x2) &&
            float.TryParse(values[3], out float y2)
        )
        {
            CalculateError(x1, y1, x2, y2);
        }
    }

    void CalculateError(
        float x1,
        float y1,
        float x2,
        float y2
    )
    {
        float beaconX = (x1 + x2) / 2f;
        float beaconY = (y1 + y2) / 2f;

        float cameraX = width / 2f;
        float cameraY = height / 2f;

        float errorX = beaconX - cameraX;
        float errorY = beaconY - cameraY;

        Debug.Log(
            $"Beacon: ({beaconX:F1}, {beaconY:F1}) | " +
            $"Error: ({errorX:F1}, {errorY:F1})"
        );

        // Send error to UI
        if (trackingMetrics != null)
        {
            trackingMetrics.UpdateError(errorX, errorY);
        }

        MoveCamera(errorX, errorY);
    }

    void MoveCamera(float errorX, float errorY)
    {
        // Dead zone
        if (Mathf.Abs(errorX) < 5f)
            errorX = 0f;

        if (Mathf.Abs(errorY) < 5f)
            errorY = 0f;

        // Calculate movement in degrees
        float pan = errorX * panGain;
        float tilt = -errorY * tiltGain;

        // Limit maximum movement
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

        // Move camera
        cam.transform.Rotate(
            -tilt,
            pan,
            0f,
            Space.Self
        );

        // Send the camera's ACTUAL current orientation
        SendPanTilt();
    }

    void SendPanTilt()
    {
        if (stream == null)
            return;

        Vector3 rotation = cam.transform.localEulerAngles;

        // Convert Unity's 0-360 degree representation
        // into a signed -180 to +180 representation.
        float pan = NormalizeAngle(rotation.y);
        float tilt = NormalizeAngle(rotation.x);

        string message =
            $"PANTILT,{pan:F4},{tilt:F4}\n";

        byte[] data = Encoding.UTF8.GetBytes(message);

        // Message type 2 = pan/tilt
        byte[] messageType = new byte[] { 2 };

        try
        {
            stream.Write(messageType, 0, 1);
            stream.Write(data, 0, data.Length);
        }
        catch (System.Exception e)
        {
            Debug.LogError(
                "Failed to send pan/tilt: " + e.Message
            );
        }
    }

    float NormalizeAngle(float angle)
    {
        if (angle > 180f)
            angle -= 360f;

        return angle;
    }

    void OnDestroy()
    {
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