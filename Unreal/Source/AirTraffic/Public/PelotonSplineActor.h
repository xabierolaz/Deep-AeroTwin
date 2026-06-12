#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PelotonSplineActor.generated.h"

class UChildActorComponent;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class USceneComponent;
class USplineComponent;
class UStaticMesh;
class UStaticMeshComponent;

UENUM(BlueprintType)
enum class EPelotonRiderRenderMode : uint8
{
	StaticMeshComponents UMETA(DisplayName = "Static Mesh Components (Clean Motion)"),
	InstancedStaticMesh UMETA(DisplayName = "Instanced Static Mesh (Performance)"),
	ChildActorBlueprint UMETA(DisplayName = "Child Actor Blueprint"),
};

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

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Peloton")
	TObjectPtr<UInstancedStaticMeshComponent> RiderMeshInstances;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Peloton|Riders")
	TObjectPtr<UStaticMesh> RiderStaticMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Peloton|Riders")
	TObjectPtr<UMaterialInterface> RiderMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Peloton|Riders")
	TSubclassOf<AActor> RiderClass;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders")
	EPelotonRiderRenderMode RiderRenderMode = EPelotonRiderRenderMode::StaticMeshComponents;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders|Optimization")
	bool bRidersCastShadows = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Riders", meta = (ClampMin = "1", ClampMax = "64"))
	int32 RiderCount = 14;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (ClampMin = "1", ClampMax = "8"))
	int32 MaxRidersPerRow = 5;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (ClampMin = "0.0", Units = "cm"))
	float LongitudinalSpacing = 220.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (ClampMin = "0.0", Units = "cm"))
	float LateralSpacing = 95.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (Units = "cm"))
	float AlternateRowLateralStagger = 35.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Formation", meta = (Units = "cm"))
	float RiderZOffset = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Movement", meta = (ClampMin = "0.0", Units = "cm/s"))
	float SpeedCmPerSecond = 850.0f;

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

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts")
	bool bShowForwardLeaderGhosts = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts")
	bool bShowBackwardLastGhosts = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "0.0", Units = "cm"))
	float ForwardGhostDistance = 1800.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "0.0", Units = "cm"))
	float BackwardGhostDistance = 1800.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "0.0", Units = "cm"))
	float ForwardGhostStartOffset = 250.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "0.0", Units = "cm"))
	float BackwardGhostStartOffset = 250.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "1.0", Units = "cm"))
	float GhostSpacing = 300.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "0", ClampMax = "32"))
	int32 MaxGhostsPerSide = 8;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float GhostMaxOpacity = 0.38f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float GhostMinOpacity = 0.1f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts|Heatmap")
	bool bUseGhostHeatmap = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts|Heatmap")
	FLinearColor GhostHotColor = FLinearColor(1.0f, 0.0f, 0.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts|Heatmap")
	FLinearColor GhostMidColor = FLinearColor(0.0f, 1.0f, 0.08f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts|Heatmap")
	FLinearColor GhostColdColor = FLinearColor(0.0f, 0.08f, 1.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts")
	FLinearColor ForwardGhostColor = FLinearColor(1.0f, 0.0f, 0.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Peloton|Ghosts")
	FLinearColor BackwardGhostColor = FLinearColor(0.0f, 0.32f, 1.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Peloton|Ghosts")
	TObjectPtr<UMaterialInterface> GhostMaterial;

	UFUNCTION(BlueprintCallable, Category = "Peloton")
	void RebuildPeloton();

	UFUNCTION(BlueprintCallable, Category = "Peloton")
	void SetPreviewDistance(float Distance);

private:
	UPROPERTY(Transient)
	TArray<TObjectPtr<UChildActorComponent>> RiderComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> RiderMeshComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> ForwardGhostComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> BackwardGhostComponents;

	float RuntimeLeadDistance = 0.0f;

	void DestroyRiderComponents();
	void DestroyRiderMeshComponents();
	void DestroyGhostComponents(TArray<TObjectPtr<UStaticMeshComponent>>& GhostComponents);
	void EnsureRiderComponents();
	void EnsureGhostComponents();
	void UpdateRiderTransforms(float LeadDistance);
	void UpdateGhostTransforms(float LeadDistance, int32 ActiveRiderCount);
	void UpdateGhostComponent(UStaticMeshComponent* GhostComponent, float Distance, float LateralOffset, float Opacity);
	void ApplyRiderMaterial(UStaticMeshComponent* RiderMeshComponent) const;
	void ApplyGhostMaterial(UStaticMeshComponent* GhostComponent);
	void RefreshGhostMaterials();
	void UpdateGhostMaterialParameters(UStaticMeshComponent* GhostComponent, const FLinearColor& Color, float Opacity);
	int32 GetRiderMaterialSlotCount() const;
	FVector2D GetFormationOffset(int32 RiderIndex) const;
	float GetGhostOpacity(float FadeRatio) const;
	FLinearColor GetGhostHeatmapColor(float FadeRatio) const;
	int32 GetGhostCount(float Distance) const;
	float NormalizeSplineDistance(float Distance) const;
	bool CanBuildRiderComponents() const;
};
