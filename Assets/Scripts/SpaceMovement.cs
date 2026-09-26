using UnityEngine;

public class SpaceMovement : MonoBehaviour
{
    [Header("Forward Movement")]
    public float speed = 0.5f;

    [Header("Arc Movement")]
    public bool useArcMovement = true;
    public float arcStrength = 0.15f;

    [Header("Satellite Rotation")]
    public bool enableRotation = false;
    public Vector3 rotationAxis = Vector3.up;
    public float rotationSpeed = 2f;
    public float minRotationAngle = -20f;
    public float maxRotationAngle = 20f;

    [Header("Turbulence")]
    [Range(0f, 1f)]
    public float turbulenceStrength = 0f;

    public float turbulenceSpeed = 2f;
    public float turbulenceChangeTime = 1.5f;

    private float currentAngle = 0f;
    private int rotationDirection = 1;

    private Vector3 turbulenceDirection = Vector3.zero;
    private Vector3 targetTurbulenceDirection = Vector3.zero;

    private float turbulenceTimer = 0f;


    private void Start()
    {
        currentAngle = 0f;

        ChooseNewTurbulenceDirection();
    }


    private void Update()
    {
        MoveForward();

        if (enableRotation)
        {
            RotateBackAndForth();
        }

        UpdateTurbulence();
    }


    void MoveForward()
    {
        Vector3 forwardMovement =
            transform.forward * speed;

        Vector3 arcMovement =
            Vector3.zero;

        if (useArcMovement)
        {
            arcMovement =
                transform.right * arcStrength;
        }

        Vector3 turbulenceMovement =
            turbulenceDirection *
            turbulenceStrength;

        transform.position +=
            (
                forwardMovement +
                arcMovement +
                turbulenceMovement
            )
            * Time.deltaTime;
    }


    void RotateBackAndForth()
    {
        float rotationAmount =
            rotationDirection *
            rotationSpeed *
            Time.deltaTime;

        currentAngle += rotationAmount;

        if (currentAngle >= maxRotationAngle)
        {
            currentAngle = maxRotationAngle;
            rotationDirection = -1;
        }
        else if (currentAngle <= minRotationAngle)
        {
            currentAngle = minRotationAngle;
            rotationDirection = 1;
        }

        Quaternion rotation =
            Quaternion.AngleAxis(
                currentAngle,
                rotationAxis
            );

        transform.localRotation = rotation;
    }


    void UpdateTurbulence()
    {
        if (turbulenceStrength <= 0f)
        {
            turbulenceDirection = Vector3.zero;
            turbulenceTimer = 0f;

            return;
        }

        turbulenceTimer += Time.deltaTime;

        // Choose a new random direction
        if (turbulenceTimer >= turbulenceChangeTime)
        {
            turbulenceTimer = 0f;

            ChooseNewTurbulenceDirection();
        }

        // Move smoothly toward the new direction
        turbulenceDirection =
            Vector3.Lerp(
                turbulenceDirection,
                targetTurbulenceDirection,
                Time.deltaTime * turbulenceSpeed
            );
    }


    void ChooseNewTurbulenceDirection()
    {
        targetTurbulenceDirection =
            Random.insideUnitSphere.normalized;
    }


    public void SetTurbulence(float value)
    {
        turbulenceStrength =
            Mathf.Clamp01(value);
    }
}