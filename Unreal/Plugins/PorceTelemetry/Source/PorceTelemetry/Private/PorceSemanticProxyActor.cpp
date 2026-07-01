#include "PorceSemanticProxyActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

APorceSemanticProxyActor::APorceSemanticProxyActor()
{
    PrimaryActorTick.bCanEverTick = false;

    ProxyRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SPPAProxyRoot"));
    RootComponent = ProxyRoot;

    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereFinder(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderFinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeFinder(TEXT("/Engine/BasicShapes/Cone.Cone"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));

    CubeMesh = CubeFinder.Object;
    SphereMesh = SphereFinder.Object;
    CylinderMesh = CylinderFinder.Object;
    ConeMesh = ConeFinder.Object;
    BasicShapeMaterial = MaterialFinder.Object;
}

void APorceSemanticProxyActor::ConfigureProxy(const FString& ClassName, float Confidence, bool bConfirmed)
{
    const FString TypeKey = ClassName.TrimStartAndEnd().ToLower();
    const float ConfidenceAlpha = FMath::Clamp(Confidence, 0.0f, 1.0f);
    const int32 ConfidenceBucket = FMath::RoundToInt(ConfidenceAlpha * 20.0f);
    if (
        GeneratedComponents.Num() > 0
        && LastConfiguredClassKey == TypeKey
        && LastConfiguredConfidenceBucket == ConfidenceBucket
        && bLastConfiguredConfirmed == bConfirmed
    )
    {
        return;
    }

    ClearProxy();
    LastConfiguredClassKey = TypeKey;
    LastConfiguredConfidenceBucket = ConfidenceBucket;
    bLastConfiguredConfirmed = bConfirmed;

    FLinearColor Color = bConfirmed ? ConfirmedColor : TentativeColor;
    Color.A = FMath::Lerp(0.45f, 1.0f, ConfidenceAlpha);

    if (TypeKey == TEXT("tower"))
    {
        BuildTowerProxy(Color, bConfirmed);
    }
    else if (TypeKey == TEXT("cow"))
    {
        BuildCowProxy(Color, bConfirmed);
    }
    else if (
        TypeKey == TEXT("bike")
        || TypeKey == TEXT("biker")
        || TypeKey == TEXT("person")
        || TypeKey == TEXT("bicycle")
    )
    {
        BuildBikerProxy(Color, bConfirmed);
    }
    else
    {
        FLinearColor FallbackColor = UnknownColor;
        FallbackColor.A = Color.A;
        BuildUnknownProxy(FallbackColor, bConfirmed);
    }

    Tags.AddUnique(TEXT("PORCE_SPPA_PROXY"));
    Tags.AddUnique(*FString::Printf(TEXT("PORCE_CLASS_%s"), *TypeKey));
}

void APorceSemanticProxyActor::ClearProxy()
{
    for (UStaticMeshComponent* Component : GeneratedComponents)
    {
        if (IsValid(Component))
        {
            Component->DestroyComponent();
        }
    }
    GeneratedComponents.Empty();
}

UStaticMesh* APorceSemanticProxyActor::ResolveMesh(const FName& ShapeName) const
{
    if (ShapeName == TEXT("sphere"))
    {
        return SphereMesh;
    }
    if (ShapeName == TEXT("cylinder"))
    {
        return CylinderMesh;
    }
    if (ShapeName == TEXT("cone"))
    {
        return ConeMesh;
    }
    return CubeMesh;
}

UStaticMeshComponent* APorceSemanticProxyActor::AddPart(
    const FName& ShapeName,
    const FName& PartName,
    const FVector& RelativeLocation,
    const FRotator& RelativeRotation,
    const FVector& RelativeScale,
    const FLinearColor& Color,
    bool bConfirmed
)
{
    UStaticMesh* Mesh = ResolveMesh(ShapeName);
    if (!IsValid(Mesh))
    {
        return nullptr;
    }

    const FName ComponentName = MakeUniqueObjectName(this, UStaticMeshComponent::StaticClass(), PartName);
    UStaticMeshComponent* Component = NewObject<UStaticMeshComponent>(this, ComponentName);
    if (!IsValid(Component))
    {
        return nullptr;
    }

    Component->SetupAttachment(ProxyRoot);
    Component->SetStaticMesh(Mesh);
    Component->SetRelativeLocation(RelativeLocation);
    Component->SetRelativeRotation(RelativeRotation);
    Component->SetRelativeScale3D(RelativeScale);
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetCollisionEnabled((bConfirmed && bEnableCollisionForConfirmed) ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
    Component->SetGenerateOverlapEvents(false);

    if (IsValid(BasicShapeMaterial))
    {
        UMaterialInstanceDynamic* DynamicMaterial = UMaterialInstanceDynamic::Create(BasicShapeMaterial, this);
        if (IsValid(DynamicMaterial))
        {
            DynamicMaterial->SetVectorParameterValue(TEXT("Color"), Color);
            Component->SetMaterial(0, DynamicMaterial);
        }
        else
        {
            Component->SetMaterial(0, BasicShapeMaterial);
        }
    }

    Component->RegisterComponent();
    AddInstanceComponent(Component);
    GeneratedComponents.Add(Component);
    return Component;
}

void APorceSemanticProxyActor::BuildBikerProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cylinder"), TEXT("WheelFront"), FVector(48.0f, 0.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.32f), Color, bConfirmed);
    AddPart(TEXT("cylinder"), TEXT("WheelRear"), FVector(-48.0f, 0.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.32f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("BikeFrame"), FVector(0.0f, 0.0f, 82.0f), FRotator(0.0f, 0.0f, 0.0f), FVector(1.05f, 0.10f, 0.10f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("BikeFork"), FVector(34.0f, 0.0f, 90.0f), FRotator(0.0f, 0.0f, -32.0f), FVector(0.12f, 0.10f, 0.70f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("RiderBody"), FVector(0.0f, 0.0f, 150.0f), FRotator(0.0f, 0.0f, -10.0f), FVector(0.28f, 0.20f, 0.82f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("RiderHead"), FVector(10.0f, 0.0f, 205.0f), FRotator::ZeroRotator, FVector(0.24f, 0.24f, 0.24f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildCowProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("sphere"), TEXT("CowBody"), FVector(0.0f, 0.0f, 95.0f), FRotator::ZeroRotator, FVector(0.92f, 0.42f, 0.38f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("CowHead"), FVector(78.0f, 0.0f, 120.0f), FRotator::ZeroRotator, FVector(0.30f, 0.24f, 0.26f), Color, bConfirmed);
    AddPart(TEXT("cone"), TEXT("CowDirection"), FVector(112.0f, 0.0f, 122.0f), FRotator(0.0f, 90.0f, 0.0f), FVector(0.18f, 0.18f, 0.30f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegFL"), FVector(42.0f, 20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegFR"), FVector(42.0f, -20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegRL"), FVector(-42.0f, 20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegRR"), FVector(-42.0f, -20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildTowerProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cylinder"), TEXT("TowerMast"), FVector(0.0f, 0.0f, 210.0f), FRotator::ZeroRotator, FVector(0.22f, 0.22f, 4.20f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("TowerTopCrossbar"), FVector(0.0f, 0.0f, 430.0f), FRotator::ZeroRotator, FVector(1.70f, 0.12f, 0.12f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("TowerMidCrossbar"), FVector(0.0f, 0.0f, 310.0f), FRotator::ZeroRotator, FVector(1.30f, 0.10f, 0.10f), Color, bConfirmed);
    AddPart(TEXT("cone"), TEXT("TowerApex"), FVector(0.0f, 0.0f, 480.0f), FRotator::ZeroRotator, FVector(0.55f, 0.55f, 0.75f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildUnknownProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cylinder"), TEXT("UnknownFootprint"), FVector(0.0f, 0.0f, 18.0f), FRotator::ZeroRotator, FVector(0.75f, 0.75f, 0.12f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("UnknownVolume"), FVector(0.0f, 0.0f, 82.0f), FRotator::ZeroRotator, FVector(0.70f, 0.70f, 1.10f), Color, bConfirmed);
    AddPart(TEXT("cone"), TEXT("UnknownUncertainty"), FVector(0.0f, 0.0f, 158.0f), FRotator::ZeroRotator, FVector(0.42f, 0.42f, 0.52f), Color, bConfirmed);
}
