using UnityEngine;

public class CameraObjectRotation : MonoBehaviour
{
    public Transform target;

    // Axis around which the object rotates
    public Vector3 rotationAxis = Vector3.up;


    // ==========================================
    // POSITIVE ROTATION SETTINGS
    // ==========================================

    // Object rotation required on the positive side
    public float positiveTriggerAngle = 90f;

    // Camera rotation when positive limit is reached
    public float positiveCameraRotation = 120f;


    // ==========================================
    // NEGATIVE ROTATION SETTINGS
    // ==========================================

    // Object rotation required on the negative side
    public float negativeTriggerAngle = -110f;

    // Camera rotation when negative limit is reached
    public float negativeCameraRotation = -100f;


    // ==========================================
    // CAMERA SETTINGS
    // ==========================================

    // Camera orbit speed
    public float orbitSpeed = 60f;

    // Distance between camera and target
    public float cameraDistance = 8f;


    // ==========================================
    // INTERNAL VARIABLES
    // ==========================================

    private float referenceRotation;

    private float currentOrbit = 0f;
    private float targetOrbit = 0f;

    private bool orbiting = false;


    void Start()
    {
        if (target == null)
            return;

        // Record the object's starting rotation
        referenceRotation = GetAxisRotation();

        Debug.Log(
            "Initial Object Rotation: " +
            referenceRotation
        );

        Debug.Log(
            "Camera Distance: " +
            cameraDistance
        );
    }


    void LateUpdate()
    {
        if (target == null)
            return;


        // Get current object rotation
        float currentRotation = GetAxisRotation();


        // Calculate rotation relative to the LAST reference position
        float relativeRotation = Mathf.DeltaAngle(
            referenceRotation,
            currentRotation
        );


        Debug.Log(
            "Current Rotation: " +
            currentRotation +
            " | Relative Rotation: " +
            relativeRotation
        );


        // ==========================================
        // CHECK POSITIVE ROTATION
        // ==========================================

        if (!orbiting &&
            relativeRotation >= positiveTriggerAngle)
        {
            Debug.Log(
                ">>> POSITIVE LIMIT REACHED: " +
                relativeRotation +
                "° <<<"
            );

            StartCameraOrbit(
                positiveCameraRotation,
                currentRotation
            );
        }


        // ==========================================
        // CHECK NEGATIVE ROTATION
        // ==========================================

        else if (!orbiting &&
                 relativeRotation <= negativeTriggerAngle)
        {
            Debug.Log(
                ">>> NEGATIVE LIMIT REACHED: " +
                relativeRotation +
                "° <<<"
            );

            StartCameraOrbit(
                negativeCameraRotation,
                currentRotation
            );
        }


        // ==========================================
        // CAMERA ORBIT
        // ==========================================

        if (orbiting)
        {
            float direction = Mathf.Sign(targetOrbit);


            float rotationThisFrame =
                orbitSpeed *
                Time.deltaTime *
                direction;


            currentOrbit += rotationThisFrame;


            // Prevent camera from going beyond
            // the requested rotation
            if (Mathf.Abs(currentOrbit) >=
                Mathf.Abs(targetOrbit))
            {
                rotationThisFrame =
                    targetOrbit - currentOrbit;

                currentOrbit = targetOrbit;
            }


            // Rotate camera around target
            transform.RotateAround(
                target.position,
                rotationAxis,
                rotationThisFrame
            );


            // ==========================================
            // MAINTAIN CAMERA DISTANCE
            // ==========================================

            Vector3 directionFromTarget =
                (transform.position - target.position)
                .normalized;


            // transform.position =
            //     target.position +
            //     directionFromTarget * cameraDistance;


            // Keep camera looking at target
            // transform.LookAt(target);


            // ==========================================
            // ORBIT FINISHED
            // ==========================================

            if (Mathf.Abs(currentOrbit) >=
                Mathf.Abs(targetOrbit))
            {
                orbiting = false;

                // Current object rotation becomes
                // the new reference position
                referenceRotation = GetAxisRotation();

                currentOrbit = 0f;

                Debug.Log(
                    ">>> CAMERA ORBIT FINISHED <<<"
                );

                Debug.Log(
                    "New Reference Rotation: " +
                    referenceRotation
                );

                // transform.LookAt(target);
            }
        }
        // else
        // {
        //     // transform.LookAt(target);
        // }
    }


    // ==========================================
    // START CAMERA ORBIT
    // ==========================================

    void StartCameraOrbit(
        float cameraRotation,
        float currentRotation)
    {
        orbiting = true;

        currentOrbit = 0f;

        targetOrbit = cameraRotation;

        // Make the current object position the
        // new reference position
        referenceRotation = currentRotation;


        Debug.Log(
            ">>> CAMERA ORBIT STARTED <<<"
        );

        Debug.Log(
            "Camera Rotation: " +
            cameraRotation +
            "°"
        );
    }


    // ==========================================
    // GET OBJECT ROTATION
    // ==========================================

    float GetAxisRotation()
    {
        Vector3 rotation =
            target.localEulerAngles;


        if (rotationAxis == Vector3.up)
            return rotation.y;


        if (rotationAxis == Vector3.right)
            return rotation.x;


        if (rotationAxis == Vector3.forward)
            return rotation.z;


        return rotation.y;
    }
}