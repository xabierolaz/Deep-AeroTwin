#include "PorceBenchmarkAssetActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

APorceBenchmarkAssetActor::APorceBenchmarkAssetActor()
{
    PrimaryActorTick.bCanEverTick = false;

    MeshComponent = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BenchmarkAssetMesh"));
    RootComponent = MeshComponent;
    MeshComponent->SetMobility(EComponentMobility::Movable);
    MeshComponent->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    MeshComponent->ComponentTags.AddUnique(TEXT("PORCE_BENCHMARK_PLACEHOLDER_ASSET"));

    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (CubeFinder.Succeeded())
    {
        MeshComponent->SetStaticMesh(CubeFinder.Object);
        MeshComponent->SetRelativeScale3D(FVector(0.020f, 0.020f, 0.020f));
    }

    static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    if (MaterialFinder.Succeeded())
    {
        MeshComponent->SetMaterial(0, MaterialFinder.Object);
    }

    Tags.AddUnique(TEXT("PORCE_BENCHMARK_PLACEHOLDER_ASSET"));
}
