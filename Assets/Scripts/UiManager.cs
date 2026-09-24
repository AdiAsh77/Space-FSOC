using UnityEngine;
using UnityEngine.UI;
using TMPro;


public class UiManager : MonoBehaviour
{
    public GameObject Pausemenu;
    public TMP_Text myText;
    public Material cameraImpairmentMaterial;
    public Slider noiseSlider;
    public Toggle noiseToggle;
    public Slider blurSlider;
    public Toggle blurToggle;

    public void OnNoiseSliderChanged(float value)
    {
        if (noiseToggle.isOn)
        {
            cameraImpairmentMaterial.SetFloat("_NoiseIntensity", value);
        }
    }

    public void OnNoiseToggleChanged(bool enabled)
    {
        if (enabled)
        {
            cameraImpairmentMaterial.SetFloat(
                "_NoiseIntensity",
                noiseSlider.value
            );
        }
        else
        {
            cameraImpairmentMaterial.SetFloat("_NoiseIntensity", 0f);
        }
    }


    public void OnBlurSliderChanged(float value)
    {
        if (blurToggle.isOn)
        {
            cameraImpairmentMaterial.SetFloat("_BlurStrength", value);
        }
    }

    public void OnBlurToggleChanged(bool enabled)
    {
        if (enabled)
        {
            cameraImpairmentMaterial.SetFloat(
                "_BlurStrength",
                blurSlider.value
            );
        }
        else
        {
            cameraImpairmentMaterial.SetFloat("_BlurStrength", 0f);
        }
    }

    public void OnPause()
    {
        if (Pausemenu.activeSelf == true)
        {
            Pausemenu.SetActive(false); 
            myText.text = "MENU";
        }
        else
        {
            Pausemenu.SetActive(true); 
            myText.text = "RETURN";
        }
    }



    public void SetEffects(
        float noise,
        float blur
    )
    {
        cameraImpairmentMaterial.SetFloat(
            "_NoiseIntensity",
            noise
        );

        cameraImpairmentMaterial.SetFloat(
            "_BlurStrength",
            blur
        );
    }
}
