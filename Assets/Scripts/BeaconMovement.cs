
using UnityEngine;

public class BeaconMovement : MonoBehaviour
{
    [Header("Movement")]
    public float movementSpeed = 1f;
    public float movementRange = 5f;

    [Header("Satellite Avoidance")]
    public Transform satellite;
    public float avoidanceRadius = 10f;

    private string movementType = "Mixed";

    private Vector3 startPosition;
    private Vector3 normalPosition;
    private Vector3 randomTarget;
    private Vector3 avoidanceOffset;

    private float time = 0f;


    // ============================================================
    // START
    // ============================================================

    void Start()
    {
        normalPosition = transform.position;
        startPosition = normalPosition;

        ChooseRandomTarget();
    }


    // ============================================================
    // UPDATE
    // ============================================================

    void Update()
    {
        time += Time.deltaTime * movementSpeed;

        // Calculate the normal, predefined movement first.
        switch (movementType)
        {
            case "Straight Horizontal":
                normalPosition = startPosition +
                    new Vector3(Mathf.Sin(time) * movementRange, 0f, 0f);
                break;

            case "Straight Vertical":
                normalPosition = startPosition +
                    new Vector3(0f, Mathf.Sin(time) * movementRange, 0f);
                break;

            case "Figure 8":
                normalPosition = startPosition +
                    new Vector3(
                        Mathf.Sin(time) * movementRange,
                        Mathf.Sin(time * 2f) * movementRange * 0.5f,
                        0f
                    );
                break;

            case "Circular":
                normalPosition = startPosition +
                    new Vector3(
                        Mathf.Cos(time) * movementRange,
                        Mathf.Sin(time) * movementRange,
                        0f
                    );
                break;

            case "Random":
                normalPosition = Vector3.MoveTowards(
                    normalPosition,
                    randomTarget,
                    movementSpeed * Time.deltaTime
                );

                if (Vector3.Distance(normalPosition, randomTarget) < 0.1f)
                {
                    ChooseRandomTarget();
                }
                break;

            case "Mixed":
                int pattern = Mathf.FloorToInt(time / 10f) % 4;

                if (pattern == 0)
                {
                    normalPosition = startPosition +
                        new Vector3(Mathf.Sin(time) * movementRange, 0f, 0f);
                }
                else if (pattern == 1)
                {
                    normalPosition = startPosition +
                        new Vector3(0f, Mathf.Sin(time) * movementRange, 0f);
                }
                else if (pattern == 2)
                {
                    normalPosition = startPosition +
                        new Vector3(
                            Mathf.Sin(time) * movementRange,
                            Mathf.Sin(time * 2f) * movementRange * 0.5f,
                            0f
                        );
                }
                else
                {
                    normalPosition = startPosition +
                        new Vector3(
                            Mathf.Cos(time) * movementRange,
                            Mathf.Sin(time) * movementRange,
                            0f
                        );
                }
                break;
        }

        // Apply avoidance AFTER calculating normal movement.
        ApplySatelliteAvoidance();
    }


    // ============================================================
    // SET MOVEMENT TYPE
    // ============================================================

    public void SetMovementType(string type)
    {
        // Recover the intended position, not the avoidance-adjusted
        // position, when changing movement patterns.
        normalPosition = transform.position - avoidanceOffset;
        startPosition = normalPosition;

        movementType = type;
        time = 0f;
        avoidanceOffset = Vector3.zero;

        ChooseRandomTarget();

        Debug.Log("Beacon movement type: " + movementType);
    }


    // ============================================================
    // CONFIGURE SATELLITE AVOIDANCE
    // ============================================================

    public void SetAvoidanceSphere(Transform satelliteTransform, float radius)
    {
        satellite = satelliteTransform;
        avoidanceRadius = Mathf.Max(0f, radius);

        Debug.Log(
            "Beacon avoidance configured | Radius: "
            + avoidanceRadius
        );
    }


    // ============================================================
    // KEEP BEACON OUTSIDE SATELLITE'S EXCLUSION SPHERE
    // ============================================================

    void ApplySatelliteAvoidance()
    {
        // Reset the offset every frame.
        // This prevents avoidance from permanently changing the path.
        avoidanceOffset = Vector3.zero;

        if (satellite == null || avoidanceRadius <= 0f)
        {
            transform.position = normalPosition;
            return;
        }

        Vector3 fromSatellite =
            normalPosition - satellite.position;

        float distance = fromSatellite.magnitude;

        // Beacon's intended position is outside the exclusion sphere.
        if (distance >= avoidanceRadius)
        {
            transform.position = normalPosition;
            return;
        }

        // Handle the rare case where both positions are identical.
        Vector3 direction;

        if (distance > 0.001f)
        {
            direction = fromSatellite / distance;
        }
        else
        {
            direction = startPosition - satellite.position;

            if (direction.sqrMagnitude < 0.001f)
            {
                direction = Vector3.right;
            }

            direction.Normalize();
        }

        // Move the beacon to the sphere's surface.
        Vector3 safePosition =
            satellite.position + direction * avoidanceRadius;

        avoidanceOffset = safePosition - normalPosition;

        transform.position = safePosition;
    }


    // ============================================================
    // RANDOM TARGET
    // ============================================================

    void ChooseRandomTarget()
    {
        randomTarget = startPosition +
            new Vector3(
                Random.Range(-movementRange, movementRange),
                Random.Range(-movementRange, movementRange),
                0f
            );
    }
}
