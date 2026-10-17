using UnityEngine;

public class StartPause : MonoBehaviour
{
    void Start()
    {
        // Stops all physics and time-based movements immediately on startup
        Time.timeScale = 0f; 
    }
}
