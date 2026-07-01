#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PorceSemanticProxyActor.generated.h"

class UMaterialInterface;
class UStaticMesh;
class UStaticMeshComponent;

UCLASS(Blueprintable)
class PORCETELEMETRY_API APorceSemanticProxyActor : public AActor
{
    GENERATED_BODY()

public:
    APorceSemanticProxyActor();

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|SPPA")
    void ConfigureProxy(const FString& ClassName, float Confidence, bool bConfirmed);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    bool bEnableCollisionForConfirmed = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    FLinearColor ConfirmedColor = FLinearColor(0.05f, 0.55f, 0.95f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    FLinearColor TentativeColor = FLinearColor(1.0f, 0.72f, 0.15f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    FLinearColor UnknownColor = FLinearColor(0.78f, 0.78f, 0.82f, 1.0f);

private:
    UPROPERTY(VisibleAnywhere, Category="PORCE Twin V2|SPPA")
    TObjectPtr<USceneComponent> ProxyRoot;

    UPROPERTY(Transient)
    TArray<TObjectPtr<UStaticMeshComponent>> GeneratedComponents;

    UPROPERTY(Transient)
    TObjectPtr<UStaticMesh> CubeMesh;

    UPROPERTY(Transient)
    TObjectPtr<UStaticMesh> SphereMesh;

    UPROPERTY(Transient)
    TObjectPtr<UStaticMesh> CylinderMesh;

    UPROPERTY(Transient)
    TObjectPtr<UStaticMesh> ConeMesh;

    UPROPERTY(Transient)
    TObjectPtr<UMaterialInterface> BasicShapeMaterial;

    FString LastConfiguredClassKey;
    int32 LastConfiguredConfidenceBucket = -1;
    bool bLastConfiguredConfirmed = false;

    void ClearClassTags();
    void ClearProxy();
    UStaticMesh* ResolveMesh(const FName& ShapeName) const;
    UStaticMeshComponent* AddPart(
        const FName& ShapeName,
        const FName& PartName,
        const FVector& RelativeLocation,
        const FRotator& RelativeRotation,
        const FVector& RelativeScale,
        const FLinearColor& Color,
        bool bConfirmed
    );
    void BuildBikerProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildCowProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildTowerProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildUnknownProxy(const FLinearColor& Color, bool bConfirmed);
};
