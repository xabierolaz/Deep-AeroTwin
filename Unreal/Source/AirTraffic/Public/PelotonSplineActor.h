#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PelotonSplineActor.generated.h"

class UMaterialInterface;
class USceneComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
class USplineComponent;

UCLASS(Blueprintable)
class AIRTRAFFIC_API APelotonSplineActor : public AActor
{
	GENERATED_BODY()

public:
	APelotonSplineActor();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void Tick(float DeltaSeconds) override;

#if WITH_EDITOR
	virtual bool ShouldTickIfViewportsOnly() const override;
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

protected:
	virtual void BeginPlay() override;

public:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Peloton")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Peloton")
	TObjectPtr<USplineComponent> RouteSpline;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Peloton|Riders|Textured Morph")
	TObjectPtr<USkeletalMesh> RiderSkeletalMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Peloton|Riders")
	TObjectPtr<UMaterialInterface> RiderMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Optimization")
	bool bRidersCastShadows = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Textured Morph")
	bool bAnimatePedalMorph = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Textured Morph")
	FName PedalMorphTargetName = TEXT("key_loop");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Textured Morph", meta = (ClampMin = "0.05", Units = "s"))
	float PedalCycleSeconds = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Textured Morph", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float PedalMorphMin = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Textured Morph", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float PedalMorphMax = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Textured Morph", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float PedalPhaseOffsetPerRider = 0.137f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders", meta = (ClampMin = "1", ClampMax = "64"))
	int32 RiderCount = 8;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (ClampMin = "1", ClampMax = "8"))
	int32 MaxRidersPerRow = 3;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (ClampMin = "0.0", Units = "cm"))
	float LongitudinalSpacing = 220.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (ClampMin = "0.0", Units = "cm"))
	float LateralSpacing = 95.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (Units = "cm"))
	float AlternateRowLateralStagger = 35.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (Units = "cm"))
	float RiderZOffset = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement", meta = (ClampMin = "0.0", Units = "cm/s"))
	float SpeedCmPerSecond = 640.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement", meta = (ClampMin = "0.0", Units = "cm"))
	float StartDistance = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement", meta = (ClampMin = "0.0", Units = "cm"))
	float EditorPreviewDistance = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement")
	bool bLoop = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement")
	bool bAnimateInGame = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement")
	bool bAnimateInEditor = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement")
	bool bFaceAlongSpline = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement", meta = (Units = "deg"))
	float RiderYawOffset = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement|Synchronization")
	bool bSyncToTargetActor = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement|Synchronization")
	bool bSyncToPlayerCamera = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement|Synchronization")
	FString SyncTargetActorLabel = TEXT("BP_AirplaneMarker");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement|Synchronization")
	FVector SyncApproachDirection = FVector(1.0f, 0.0f, 0.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement|Synchronization", meta = (ClampMin = "1.0", Units = "cm/s"))
	float SyncTargetSpeedCmPerSecond = 700.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement|Synchronization", meta = (ClampMin = "0.0", Units = "cm"))
	float SyncCrossingDistance = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement|Synchronization", meta = (Units = "cm"))
	float SyncPhaseOffset = 0.0f;

	UFUNCTION(BlueprintCallable, Category = "Peloton")
	void RebuildPeloton();

	UFUNCTION(BlueprintCallable, Category = "Peloton")
	void SetPreviewDistance(float Distance);

private:
	UPROPERTY(Transient)
	TArray<TObjectPtr<USkeletalMeshComponent>> RiderSkeletalMeshComponents;

	UPROPERTY(Transient)
	TWeakObjectPtr<AActor> CachedSyncTargetActor;

	float RuntimeLeadDistance = 0.0f;
	float LastSyncDebugLogTimeSeconds = -1000.0f;

	void DestroyRiderSkeletalMeshComponents();
	void DestroyLegacyComponents();
	void EnsureRiderComponents();
	void UpdateRiderTransforms(float LeadDistance);
	void ApplyRiderMaterial(USkeletalMeshComponent* RiderMeshComponent) const;
	void UpdatePedalMorph(USkeletalMeshComponent* RiderMeshComponent, int32 RiderIndex) const;
	AActor* ResolveSyncTargetActor();
	bool UpdateSynchronizedLeadDistance();
	FVector2D GetFormationOffset(int32 RiderIndex) const;
	float NormalizeSplineDistance(float Distance) const;
	bool CanBuildRiderComponents() const;
};
