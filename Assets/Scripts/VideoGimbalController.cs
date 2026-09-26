using UnityEngine;

public class VideoGimbalController : MonoBehaviour
{
    public void SetPanTilt(float pan, float tilt)
    {
        transform.localRotation =
            Quaternion.Euler(tilt, pan, 0f);
    }
}