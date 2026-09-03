using UnityEngine;

public class FloatingAsteroid : MonoBehaviour
{
    [Header("Movement")]
    public float speed = 0.5f;

    [Tooltip("Minimum time before changing direction")]
    public float minDirectionChangeInterval = 3f;

    [Tooltip("Maximum time before changing direction")]
    public float maxDirectionChangeInterval = 8f;

    [Header("Rotation")]
    public float rotationSpeed = 10f;

    private Vector3 direction;
    private Vector3 rotationAxis;
    private float timer;
    private float directionChangeInterval;

    void Start()
    {
        // Random starting movement direction
        direction = Random.onUnitSphere;

        // Random fixed rotation axis
        rotationAxis = Random.onUnitSphere;

        // Random initial direction-change time
        directionChangeInterval = Random.Range(
            minDirectionChangeInterval,
            maxDirectionChangeInterval
        );

        timer = directionChangeInterval;
    }

    void Update()
    {
        // Move asteroid
        transform.position += direction * speed * Time.deltaTime;

        // Smoothly rotate around one fixed random axis
        transform.Rotate(
            rotationAxis,
            rotationSpeed * Time.deltaTime,
            Space.Self
        );

        // Countdown to direction change
        timer -= Time.deltaTime;

        if (timer <= 0f)
        {
            // Pick a new movement direction
            direction = Random.onUnitSphere;

            // Pick a new random interval
            directionChangeInterval = Random.Range(
                minDirectionChangeInterval,
                maxDirectionChangeInterval
            );

            timer = directionChangeInterval;
        }
    }
}