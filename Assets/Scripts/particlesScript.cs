using System.Collections;
using System.Collections.Generic;
using UnityEngine;
[RequireComponent(typeof(ParticleSystem))]
public class particlesScript: MonoBehaviour
{
    ParticleSystem.Particle[] particles;
    ParticleSystem particleSystem;
    int numAlive;
    bool itRan;
    // Start is called before the first frame update

    void LateUpdate()
    {
        InitializeIfNeeded();
        particleSystem = GetComponent<ParticleSystem>();
        ParticleSystem.EmitParams emitOverride = new ParticleSystem.EmitParams();
        particleSystem.SetParticles (particles, numAlive);
        particleSystem.Emit(emitOverride, 5000);
        numAlive = particleSystem.GetParticles(particles);
        if (itRan == false)
        {
            Callonce();    
        }
    }
    private void Callonce()
    {
        for (int i = 0; i < particles.Length; i++)
        {
            //Set position of the particles
            particles[i].position = new Vector3(Random.Range(-700f, 700f), Random.Range(-900, 900f), Random.Range(900f, 3000f));
            particles[i].velocity = new Vector3(0, 0, 0);
        }
        itRan = true;
    }
    void InitializeIfNeeded()
    {
        if (particleSystem == null)
        particleSystem = GetComponent<ParticleSystem>();
        if (particles == null || particles.Length < particleSystem.main.maxParticles)
        particles = new ParticleSystem.Particle[particleSystem.main.maxParticles];
    }
}