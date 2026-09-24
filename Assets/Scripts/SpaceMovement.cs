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

    public float minTurbulenceChangeTime = 5f;
    public float maxTurbulenceChangeTime = 10f;

    private float currentAngle = 0f;
    private int rotationDirection = 1;

    private Vector3 turbulenceDirection = Vector3.zero;
    private Vector3 targetTurbulenceDirection = Vector3.zero;

    private float turbulenceTimer = 0f;
    private float nextTurbulenceChange = 5f;


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
        // No turbulence
        if (turbulenceStrength <= 0f)
        {
            turbulenceDirection = Vector3.zero;
            turbulenceTimer = 0f;

            return;
        }

        turbulenceTimer += Time.deltaTime;

        // Time to choose a new direction
        if (turbulenceTimer >= nextTurbulenceChange)
        {
            turbulenceTimer = 0f;

            ChooseNewTurbulenceDirection();
        }

        // Smoothly change towards new direction
        turbulenceDirection =
            Vector3.Lerp(
                turbulenceDirection,
                targetTurbulenceDirection,
                Time.deltaTime * 0.5f
            );
    }


    void ChooseNewTurbulenceDirection()
    {
        targetTurbulenceDirection =
            Random.onUnitSphere;

        nextTurbulenceChange =
            Random.Range(
                minTurbulenceChangeTime,
                maxTurbulenceChangeTime
            );
    }


    public void SetTurbulence(float value)
    {
        turbulenceStrength =
            Mathf.Clamp01(value);
    }
}