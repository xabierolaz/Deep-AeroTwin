#include "PorceTelemetryModule.h"

#include "PorceSppaPackagedBenchmarkRunner.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

#define LOCTEXT_NAMESPACE "FPorceTelemetryModule"

void FPorceTelemetryModule::StartupModule()
{
    bBenchmarkRunnerSpawned = false;
    BenchmarkTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateRaw(this, &FPorceTelemetryModule::HandleBenchmarkTicker),
        0.1f
    );
}

void FPorceTelemetryModule::ShutdownModule()
{
    if (BenchmarkTickerHandle.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(BenchmarkTickerHandle);
        BenchmarkTickerHandle.Reset();
    }
}

bool FPorceTelemetryModule::HandleBenchmarkTicker(float DeltaTime)
{
    if (!APorceSppaPackagedBenchmarkRunner::IsBenchmarkRequested())
    {
        return false;
    }

    if (bBenchmarkRunnerSpawned)
    {
        return false;
    }

    if (GEngine == nullptr)
    {
        return true;
    }

    for (const FWorldContext& WorldContext : GEngine->GetWorldContexts())
    {
        UWorld* World = WorldContext.World();
        if (World == nullptr || !World->IsGameWorld())
        {
            continue;
        }

        FActorSpawnParameters SpawnParameters;
        SpawnParameters.Name = MakeUniqueObjectName(
            World->GetCurrentLevel(),
            APorceSppaPackagedBenchmarkRunner::StaticClass(),
            TEXT("PorceSPPAPackagedBenchmarkRunner")
        );
        SpawnParameters.ObjectFlags |= RF_Transient;

        APorceSppaPackagedBenchmarkRunner* Runner = World->SpawnActor<APorceSppaPackagedBenchmarkRunner>(
            APorceSppaPackagedBenchmarkRunner::StaticClass(),
            FVector::ZeroVector,
            FRotator::ZeroRotator,
            SpawnParameters
        );

        if (IsValid(Runner))
        {
            bBenchmarkRunnerSpawned = true;
            UE_LOG(LogTemp, Display, TEXT("PORCE_SPPA_PACKAGED_BENCHMARK_RUNNER_SPAWNED world=%s"), *World->GetName());
            return false;
        }

        UE_LOG(LogTemp, Warning, TEXT("PORCE_SPPA_PACKAGED_BENCHMARK_RUNNER_SPAWN_FAILED world=%s"), *World->GetName());
    }

    return true;
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FPorceTelemetryModule, PorceTelemetry)
