#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PorceBenchmarkAssetActor.generated.h"

class UStaticMeshComponent;

UCLASS(Blueprintable)
class PORCETELEMETRY_API APorceBenchmarkAssetActor : public AActor
{
    GENERATED_BODY()

public:
    APorceBenchmarkAssetActor();

private:
    UPROPERTY(VisibleAnywhere, Category="PORCE Twin V2|Benchmark")
    TObjectPtr<UStaticMeshComponent> MeshComponent;
};
