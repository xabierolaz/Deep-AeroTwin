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

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|SPPA")
    bool ConfigureProxyFromDescriptorJson(const FString& DescriptorJson, bool bConfirmed = false);

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|SPPA")
    bool ApplyProxyUpdatePacketJson(const FString& UpdatePacketJson, bool bConfirmed = false);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    bool bEnableCollisionForConfirmed = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    FLinearColor ConfirmedColor = FLinearColor(0.05f, 0.55f, 0.95f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    FLinearColor TentativeColor = FLinearColor(1.0f, 0.72f, 0.15f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    FLinearColor UnknownColor = FLinearColor(0.78f, 0.78f, 0.82f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    bool bUseEvidenceCalibratedMaterials = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    float DescriptorMetersToCentimeters = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|SPPA")
    int32 MaxDescriptorParts = 128;

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
    bool bLastConfiguredUseEvidenceMaterials = true;
    FString LastConfiguredDescriptorId;
    FString LastConfiguredDescriptorAction;
    bool bHasDescriptorReferenceDimsM = false;
    FVector DescriptorReferenceDimsM = FVector::OneVector;
    FVector LastAppliedDescriptorScale = FVector::OneVector;
    float CurrentConfidenceAlpha = 1.0f;
    bool bCurrentProxyUsesFallback = false;

    void ClearClassTags();
    void ClearProxy();
    UStaticMesh* ResolveMesh(const FName& ShapeName) const;
    FName ResolveMaterialRole(const FName& PartName) const;
    FName ResolveEvidenceSource() const;
    FName ResolveUncertaintyStyle(const FName& MaterialRole) const;
    FLinearColor ResolvePartColor(const FName& PartName, const FLinearColor& BaseColor) const;
    FLinearColor ResolveMaterialColor(const FName& MaterialRole, const FName& EvidenceSource, const FName& UncertaintyStyle, const FLinearColor& BaseColor) const;
    bool TryInferDescriptorReferenceDimsM(FVector& OutDimsM) const;
    UStaticMeshComponent* AddPart(
        const FName& ShapeName,
        const FName& PartName,
        const FVector& RelativeLocation,
        const FRotator& RelativeRotation,
        const FVector& RelativeScale,
        const FLinearColor& Color,
        bool bConfirmed,
        const FName& ExplicitMaterialRole = NAME_None,
        const FName& ExplicitEvidenceSource = NAME_None,
        const FName& ExplicitUncertaintyStyle = NAME_None
    );
    void BuildBikerProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildCowProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildVehicleProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildVegetationProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildTowerProxy(const FLinearColor& Color, bool bConfirmed);
    void BuildUnknownProxy(const FLinearColor& Color, bool bConfirmed);
};
