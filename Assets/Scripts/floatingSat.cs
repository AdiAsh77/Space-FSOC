using UnityEngine;

public class FloatingSatellite : MonoBehaviour
{
    [Header("Forward Movement")]
    public float speed = 0.2f;

    [Header("To-and-From Motion")]
    public float arcDistance = 2f;
    public float arcSpeed = 0.3f;

    private Vector3 moveDirection;
    private Vector3 arcDirection;
    private Vector3 startPosition;
    private float time;

    void Start()
    {
        startPosition = transform.position;

        // Pick one random direction for the satellite to drift
        moveDirection = Random.onUnitSphere.normalized;

        // Pick another direction for the side-to-side motion
        arcDirection = Vector3.Cross(moveDirection, Random.onUnitSphere).normalized;

        // Make sure the arc direction is valid
        if (arcDirection == Vector3.zero)
        {
            arcDirection = Vector3.up;
        }
    }

    void Update()
    {
        time += Time.deltaTime;

        // Main slow movement in one direction
        Vector3 forwardMovement = moveDirection * speed * Time.deltaTime;

        // Large smooth back-and-forth motion
        Vector3 arcMovement =
            arcDirection *
            Mathf.Sin(time * arcSpeed) *
            arcDistance;

        // Move forward while adding the arc
        transform.position += forwardMovement;

        // Apply the side-to-side offset
        transform.position +=
            arcDirection *
            (
                Mathf.Sin(time * arcSpeed) -
                Mathf.Sin((time - Time.deltaTime) * arcSpeed)
            ) *
            arcDistance;
    }
}