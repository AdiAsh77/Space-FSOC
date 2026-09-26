using UnityEngine;

public class BeaconMovement : MonoBehaviour
{
    [Header("Movement")]
    public float movementSpeed = 1f;
    public float movementRange = 5f;

    private string movementType = "Mixed";

    private Vector3 startPosition;

    private float time = 0f;

    private Vector3 randomTarget;


    // ============================================================
    // START
    // ============================================================

    void Start()
    {
        startPosition =
            transform.position;

        ChooseRandomTarget();
    }


    // ============================================================
    // UPDATE
    // ============================================================

    void Update()
    {
        time +=
            Time.deltaTime *
            movementSpeed;


        if (
            movementType == "Straight Horizontal"
        )
        {
            MoveHorizontal();
        }
        else if (
            movementType == "Straight Vertical"
        )
        {
            MoveVertical();
        }
        else if (
            movementType == "Figure 8"
        )
        {
            MoveFigure8();
        }
        else if (
            movementType == "Circular"
        )
        {
            MoveCircular();
        }
        else if (
            movementType == "Random"
        )
        {
            MoveRandom();
        }
        else if (
            movementType == "Mixed"
        )
        {
            MoveMixed();
        }
    }


    // ============================================================
    // SET MOVEMENT TYPE
    // ============================================================

    public void SetMovementType(
        string type
    )
    {
        movementType = type;

        time = 0f;

        startPosition =
            transform.position;

        Debug.Log(
            "Beacon movement type: "
            + movementType
        );
    }


    // ============================================================
    // HORIZONTAL
    //
    // ← → ← →
    // ============================================================

    void MoveHorizontal()
    {
        float x =
            Mathf.Sin(time)
            * movementRange;

        transform.position =
            startPosition
            +
            new Vector3(
                x,
                0f,
                0f
            );
    }


    // ============================================================
    // VERTICAL
    //
    // ↑ ↓ ↑ ↓
    // ============================================================

    void MoveVertical()
    {
        float y =
            Mathf.Sin(time)
            * movementRange;

        transform.position =
            startPosition
            +
            new Vector3(
                0f,
                y,
                0f
            );
    }


    // ============================================================
    // FIGURE 8
    // ============================================================

    void MoveFigure8()
    {
        float x =
            Mathf.Sin(time)
            * movementRange;

        float y =
            Mathf.Sin(time * 2f)
            * movementRange
            * 0.5f;

        transform.position =
            startPosition
            +
            new Vector3(
                x,
                y,
                0f
            );
    }


    // ============================================================
    // CIRCULAR
    // ============================================================

    void MoveCircular()
    {
        float x =
            Mathf.Cos(time)
            * movementRange;

        float y =
            Mathf.Sin(time)
            * movementRange;

        transform.position =
            startPosition
            +
            new Vector3(
                x,
                y,
                0f
            );
    }


    // ============================================================
    // RANDOM
    // ============================================================

    void MoveRandom()
    {
        transform.position =
            Vector3.MoveTowards(
                transform.position,
                randomTarget,
                movementSpeed
                * Time.deltaTime
            );

        if (
            Vector3.Distance(
                transform.position,
                randomTarget
            ) < 0.1f
        )
        {
            ChooseRandomTarget();
        }
    }


    // ============================================================
    // CHOOSE RANDOM TARGET
    // ============================================================

    void ChooseRandomTarget()
    {
        randomTarget =
            startPosition
            +
            new Vector3(
                Random.Range(
                    -movementRange,
                    movementRange
                ),
                Random.Range(
                    -movementRange,
                    movementRange
                ),
                0f
            );
    }


    // ============================================================
    // MIXED
    // ============================================================

    void MoveMixed()
    {
        // Randomly choose a movement pattern.
        //
        // Change this later if you want Mixed to combine
        // multiple patterns continuously.

        int pattern =
            Mathf.FloorToInt(
                time / 10f
            ) % 4;


        if (pattern == 0)
        {
            MoveHorizontal();
        }
        else if (pattern == 1)
        {
            MoveVertical();
        }
        else if (pattern == 2)
        {
            MoveFigure8();
        }
        else
        {
            MoveCircular();
        }
    }
}