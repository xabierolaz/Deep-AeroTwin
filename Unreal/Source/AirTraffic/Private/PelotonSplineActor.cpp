#include "PelotonSplineActor.h"

#include "Components/ChildActorComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

APelotonSplineActor::APelotonSplineActor()
{
	PrimaryActorTick.bCanEverTick = true;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);

	RouteSpline = CreateDefaultSubobject<USplineComponent>(TEXT("RouteSpline"));
	RouteSpline->SetupAttachment(SceneRoot);
	RouteSpline->bEditableWhenInherited = true;
	RouteSpline->SetClosedLoop(true);
	RouteSpline->bDrawDebug = false;
	RouteSpline->ClearSplinePoints(false);
	RouteSpline->AddSplinePoint(FVector(-900.0f, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
	RouteSpline->AddSplinePoint(FVector(0.0f, 850.0f, 0.0f), ESplineCoordinateSpace::Local, false);
	RouteSpline->AddSplinePoint(FVector(1200.0f, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
	RouteSpline->AddSplinePoint(FVector(0.0f, -850.0f, 0.0f), ESplineCoordinateSpace::Local, false);
	RouteSpline->UpdateSpline();

	RiderMeshInstances = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("RiderMeshInstances"));
	RiderMeshInstances->SetupAttachment(SceneRoot);
	RiderMeshInstances->bEditableWhenInherited = true;
	RiderMeshInstances->SetMobility(EComponentMobility::Movable);
	RiderMeshInstances->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RiderMeshInstances->SetCastShadow(false);
	RiderMeshInstances->SetReceivesDecals(false);
	RiderMeshInstances->SetComponentTickEnabled(false);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> DefaultRiderMesh(TEXT("/Game/biker_mesh"));
	if (DefaultRiderMesh.Succeeded())
	{
		RiderStaticMesh = DefaultRiderMesh.Object;
		RiderMeshInstances->SetStaticMesh(RiderStaticMesh);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DefaultRiderMaterial(TEXT("/Game/Peloton/M_PelotonRider"));
	if (DefaultRiderMaterial.Succeeded())
	{
		RiderMaterial = DefaultRiderMaterial.Object;
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DefaultGhostMaterial(TEXT("/Game/Peloton/M_PelotonGhost"));
	if (DefaultGhostMaterial.Succeeded())
	{
		GhostMaterial = DefaultGhostMaterial.Object;
	}

	static ConstructorHelpers::FClassFinder<AActor> DefaultRiderClass(TEXT("/Game/bp_biker"));
	if (DefaultRiderClass.Succeeded())
	{
		RiderClass = DefaultRiderClass.Class;
	}
}

void APelotonSplineActor::BeginPlay()
{
	Super::BeginPlay();
	RuntimeLeadDistance = NormalizeSplineDistance(StartDistance);
	EnsureRiderComponents();
	EnsureGhostComponents();
	UpdateRiderTransforms(RuntimeLeadDistance);
}

void APelotonSplineActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RebuildPeloton();
}

void APelotonSplineActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UWorld* World = GetWorld();
	if (!World || !RouteSpline)
	{
		return;
	}

	const bool bIsGameWorld = World->IsGameWorld();
	const bool bShouldAnimate = bIsGameWorld ? bAnimateInGame : bAnimateInEditor;
	if (bShouldAnimate)
	{
		RuntimeLeadDistance = NormalizeSplineDistance(RuntimeLeadDistance + SpeedCmPerSecond * DeltaSeconds);
		UpdateRiderTransforms(RuntimeLeadDistance);
	}
	else if (!bIsGameWorld)
	{
		UpdateRiderTransforms(EditorPreviewDistance);
	}
}

#if WITH_EDITOR
bool APelotonSplineActor::ShouldTickIfViewportsOnly() const
{
	return bAnimateInEditor;
}

void APelotonSplineActor::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	RebuildPeloton();
}
#endif

void APelotonSplineActor::RebuildPeloton()
{
	if (!CanBuildRiderComponents())
	{
		return;
	}

	RuntimeLeadDistance = NormalizeSplineDistance(EditorPreviewDistance);
	EnsureRiderComponents();
	EnsureGhostComponents();
	UpdateRiderTransforms(RuntimeLeadDistance);
}

void APelotonSplineActor::SetPreviewDistance(float Distance)
{
	EditorPreviewDistance = Distance;
	RuntimeLeadDistance = NormalizeSplineDistance(Distance);
	if (CanBuildRiderComponents())
	{
		UpdateRiderTransforms(RuntimeLeadDistance);
	}
}

void APelotonSplineActor::DestroyRiderComponents()
{
	for (UChildActorComponent* RiderComponent : RiderComponents)
	{
		if (RiderComponent)
		{
			RiderComponent->DestroyChildActor();
			RiderComponent->DestroyComponent();
		}
	}
	RiderComponents.Reset();
}

void APelotonSplineActor::DestroyRiderMeshComponents()
{
	for (UStaticMeshComponent* RiderMeshComponent : RiderMeshComponents)
	{
		if (RiderMeshComponent)
		{
			RiderMeshComponent->DestroyComponent();
		}
	}
	RiderMeshComponents.Reset();
}

void APelotonSplineActor::DestroyGhostComponents(TArray<TObjectPtr<UStaticMeshComponent>>& GhostComponents)
{
	for (UStaticMeshComponent* GhostComponent : GhostComponents)
	{
		if (GhostComponent)
		{
			GhostComponent->DestroyComponent();
		}
	}
	GhostComponents.Reset();
}

void APelotonSplineActor::EnsureRiderComponents()
{
	if (!CanBuildRiderComponents())
	{
		return;
	}

	const int32 SafeRiderCount = FMath::Clamp(RiderCount, 1, 64);
	if (RiderStaticMesh && RiderRenderMode == EPelotonRiderRenderMode::StaticMeshComponents)
	{
		DestroyRiderComponents();
		if (RiderMeshInstances)
		{
			RiderMeshInstances->ClearInstances();
		}

		if (RiderMeshComponents.Num() != SafeRiderCount)
		{
			DestroyRiderMeshComponents();
			for (int32 RiderIndex = 0; RiderIndex < SafeRiderCount; ++RiderIndex)
			{
				const FName ComponentName(*FString::Printf(TEXT("PelotonRiderMesh_%02d"), RiderIndex + 1));
				UStaticMeshComponent* RiderMeshComponent = NewObject<UStaticMeshComponent>(this, ComponentName);
				RiderMeshComponent->CreationMethod = EComponentCreationMethod::UserConstructionScript;
				RiderMeshComponent->SetStaticMesh(RiderStaticMesh);
				ApplyRiderMaterial(RiderMeshComponent);
				RiderMeshComponent->SetMobility(EComponentMobility::Movable);
				RiderMeshComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				RiderMeshComponent->SetCastShadow(bRidersCastShadows);
				RiderMeshComponent->SetReceivesDecals(false);
				RiderMeshComponent->SetComponentTickEnabled(false);
				RiderMeshComponent->SetupAttachment(SceneRoot);
				RiderMeshComponent->RegisterComponent();
				AddInstanceComponent(RiderMeshComponent);
				RiderMeshComponents.Add(RiderMeshComponent);
			}
		}

		for (UStaticMeshComponent* RiderMeshComponent : RiderMeshComponents)
		{
			if (RiderMeshComponent && RiderMeshComponent->GetStaticMesh() != RiderStaticMesh)
			{
				RiderMeshComponent->SetStaticMesh(RiderStaticMesh);
			}
			RiderMeshComponent->SetCastShadow(bRidersCastShadows);
			RiderMeshComponent->SetReceivesDecals(false);
			RiderMeshComponent->SetComponentTickEnabled(false);
			ApplyRiderMaterial(RiderMeshComponent);
		}
		return;
	}

	DestroyRiderMeshComponents();
	if (RiderMeshInstances && RiderStaticMesh && RiderRenderMode == EPelotonRiderRenderMode::InstancedStaticMesh)
	{
		DestroyRiderComponents();
		if (RiderMeshInstances->GetStaticMesh() != RiderStaticMesh)
		{
			RiderMeshInstances->SetStaticMesh(RiderStaticMesh);
			RiderMeshInstances->ClearInstances();
		}
		RiderMeshInstances->SetCastShadow(bRidersCastShadows);
		RiderMeshInstances->SetReceivesDecals(false);
		RiderMeshInstances->SetComponentTickEnabled(false);
		ApplyRiderMaterial(RiderMeshInstances);

		while (RiderMeshInstances->GetInstanceCount() < SafeRiderCount)
		{
			RiderMeshInstances->AddInstance(FTransform::Identity);
		}
		while (RiderMeshInstances->GetInstanceCount() > SafeRiderCount)
		{
			RiderMeshInstances->RemoveInstance(RiderMeshInstances->GetInstanceCount() - 1);
		}
		return;
	}

	if (RiderMeshInstances)
	{
		RiderMeshInstances->ClearInstances();
	}

	if (!RiderClass)
	{
		DestroyRiderComponents();
		return;
	}

	if (RiderComponents.Num() != SafeRiderCount)
	{
		DestroyRiderComponents();
		for (int32 RiderIndex = 0; RiderIndex < SafeRiderCount; ++RiderIndex)
		{
			const FName ComponentName(*FString::Printf(TEXT("PelotonRider_%02d"), RiderIndex + 1));
			UChildActorComponent* RiderComponent = NewObject<UChildActorComponent>(this, ComponentName);
			RiderComponent->CreationMethod = EComponentCreationMethod::UserConstructionScript;
			RiderComponent->SetChildActorClass(RiderClass);
			RiderComponent->SetupAttachment(SceneRoot);
			RiderComponent->RegisterComponent();
			AddInstanceComponent(RiderComponent);
			RiderComponents.Add(RiderComponent);
		}
	}

	for (UChildActorComponent* RiderComponent : RiderComponents)
	{
		if (RiderComponent && RiderComponent->GetChildActorClass() != RiderClass)
		{
			RiderComponent->SetChildActorClass(RiderClass);
		}
	}
}

void APelotonSplineActor::EnsureGhostComponents()
{
	if (!CanBuildRiderComponents() || !RiderStaticMesh)
	{
		DestroyGhostComponents(ForwardGhostComponents);
		DestroyGhostComponents(BackwardGhostComponents);
		return;
	}

	const int32 ForwardGhostCount = bShowForwardLeaderGhosts ? GetGhostCount(ForwardGhostDistance) : 0;
	const int32 BackwardGhostCount = bShowBackwardLastGhosts ? GetGhostCount(BackwardGhostDistance) : 0;
	auto EnsureGhostArray = [this](TArray<TObjectPtr<UStaticMeshComponent>>& GhostComponents, int32 DesiredCount, const TCHAR* Prefix)
	{
		if (GhostComponents.Num() != DesiredCount)
		{
			DestroyGhostComponents(GhostComponents);
			for (int32 GhostIndex = 0; GhostIndex < DesiredCount; ++GhostIndex)
			{
				const FName ComponentName(*FString::Printf(TEXT("%s_%02d"), Prefix, GhostIndex + 1));
				UStaticMeshComponent* GhostComponent = NewObject<UStaticMeshComponent>(this, ComponentName);
				GhostComponent->CreationMethod = EComponentCreationMethod::UserConstructionScript;
				GhostComponent->SetStaticMesh(RiderStaticMesh);
				GhostComponent->SetMobility(EComponentMobility::Movable);
				GhostComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				GhostComponent->SetCastShadow(false);
				GhostComponent->SetReceivesDecals(false);
				GhostComponent->SetComponentTickEnabled(false);
				GhostComponent->SetupAttachment(SceneRoot);
				GhostComponent->RegisterComponent();
				AddInstanceComponent(GhostComponent);
				ApplyGhostMaterial(GhostComponent);
				GhostComponents.Add(GhostComponent);
			}
		}

		for (UStaticMeshComponent* GhostComponent : GhostComponents)
		{
			if (!GhostComponent)
			{
				continue;
			}
			if (GhostComponent->GetStaticMesh() != RiderStaticMesh)
			{
				GhostComponent->SetStaticMesh(RiderStaticMesh);
			}
			GhostComponent->SetCastShadow(false);
			GhostComponent->SetReceivesDecals(false);
			GhostComponent->SetComponentTickEnabled(false);
			ApplyGhostMaterial(GhostComponent);
		}
	};

	EnsureGhostArray(ForwardGhostComponents, ForwardGhostCount, TEXT("PelotonForwardGhost"));
	EnsureGhostArray(BackwardGhostComponents, BackwardGhostCount, TEXT("PelotonBackwardGhost"));
	RefreshGhostMaterials();
}

void APelotonSplineActor::UpdateRiderTransforms(float LeadDistance)
{
	const bool bUseMeshComponents = !RiderMeshComponents.IsEmpty();
	const bool bUseMeshInstances =
		RiderMeshInstances &&
		RiderStaticMesh &&
		RiderRenderMode == EPelotonRiderRenderMode::InstancedStaticMesh &&
		RiderMeshInstances->GetInstanceCount() > 0;
	if (!RouteSpline || (!bUseMeshComponents && !bUseMeshInstances && RiderComponents.IsEmpty()))
	{
		return;
	}

	const float SplineLength = RouteSpline->GetSplineLength();
	if (SplineLength <= UE_KINDA_SMALL_NUMBER)
	{
		return;
	}

	const int32 ActiveRiderCount = bUseMeshComponents
		? RiderMeshComponents.Num()
		: (bUseMeshInstances ? RiderMeshInstances->GetInstanceCount() : RiderComponents.Num());
	for (int32 RiderIndex = 0; RiderIndex < ActiveRiderCount; ++RiderIndex)
	{
		const FVector2D FormationOffset = GetFormationOffset(RiderIndex);
		const float RiderDistance = NormalizeSplineDistance(LeadDistance - FormationOffset.X);
		const FVector SplineLocation = RouteSpline->GetLocationAtDistanceAlongSpline(
			RiderDistance,
			ESplineCoordinateSpace::World);
		const FRotator SplineRotation = RouteSpline->GetRotationAtDistanceAlongSpline(
			RiderDistance,
			ESplineCoordinateSpace::World);

		const FRotationMatrix RotationMatrix(SplineRotation);
		const FVector RightVector = RotationMatrix.GetScaledAxis(EAxis::Y);
		const FVector UpVector = RotationMatrix.GetScaledAxis(EAxis::Z);
		const FVector RiderLocation =
			SplineLocation + RightVector * FormationOffset.Y + UpVector * RiderZOffset;

		FRotator RiderRotation = bFaceAlongSpline ? SplineRotation : GetActorRotation();
		RiderRotation.Yaw += RiderYawOffset;

		if (bUseMeshComponents)
		{
			UStaticMeshComponent* RiderMeshComponent = RiderMeshComponents[RiderIndex];
			if (RiderMeshComponent)
			{
				RiderMeshComponent->SetWorldLocationAndRotation(
					RiderLocation,
					RiderRotation,
					false,
					nullptr,
					ETeleportType::None);
			}
			continue;
		}

		if (bUseMeshInstances)
		{
			RiderMeshInstances->UpdateInstanceTransform(
				RiderIndex,
				FTransform(RiderRotation, RiderLocation, FVector::OneVector),
				true,
				RiderIndex == ActiveRiderCount - 1,
				false);
			continue;
		}

		UChildActorComponent* RiderComponent = RiderComponents[RiderIndex];
		if (RiderComponent)
		{
			RiderComponent->SetWorldLocationAndRotation(RiderLocation, RiderRotation);
		}
	}

	UpdateGhostTransforms(LeadDistance, ActiveRiderCount);
}

void APelotonSplineActor::UpdateGhostTransforms(float LeadDistance, int32 ActiveRiderCount)
{
	if (!RouteSpline || !RiderStaticMesh || ActiveRiderCount <= 0)
	{
		return;
	}

	for (int32 GhostIndex = 0; GhostIndex < ForwardGhostComponents.Num(); ++GhostIndex)
	{
		const float FadeRatio = ForwardGhostComponents.Num() <= 1
			? 0.0f
			: static_cast<float>(GhostIndex) / static_cast<float>(ForwardGhostComponents.Num() - 1);
		const float Opacity = GetGhostOpacity(FadeRatio);
		const float GhostDistance = LeadDistance + ForwardGhostStartOffset + static_cast<float>(GhostIndex) * GhostSpacing;
		UpdateGhostComponent(ForwardGhostComponents[GhostIndex], GhostDistance, 0.0f, Opacity);
	}

	const FVector2D LastFormationOffset = GetFormationOffset(ActiveRiderCount - 1);
	const float LastRiderDistance = LeadDistance - LastFormationOffset.X;
	for (int32 GhostIndex = 0; GhostIndex < BackwardGhostComponents.Num(); ++GhostIndex)
	{
		const float FadeRatio = BackwardGhostComponents.Num() <= 1
			? 0.0f
			: static_cast<float>(GhostIndex) / static_cast<float>(BackwardGhostComponents.Num() - 1);
		const float Opacity = GetGhostOpacity(FadeRatio);
		const float GhostDistance = LastRiderDistance - BackwardGhostStartOffset - static_cast<float>(GhostIndex) * GhostSpacing;
		UpdateGhostComponent(BackwardGhostComponents[GhostIndex], GhostDistance, LastFormationOffset.Y, Opacity);
	}
}

void APelotonSplineActor::UpdateGhostComponent(
	UStaticMeshComponent* GhostComponent,
	float Distance,
	float LateralOffset,
	float Opacity)
{
	if (!GhostComponent || !RouteSpline)
	{
		return;
	}

	const float GhostDistance = NormalizeSplineDistance(Distance);
	const FVector SplineLocation = RouteSpline->GetLocationAtDistanceAlongSpline(
		GhostDistance,
		ESplineCoordinateSpace::World);
	const FRotator SplineRotation = RouteSpline->GetRotationAtDistanceAlongSpline(
		GhostDistance,
		ESplineCoordinateSpace::World);

	const FRotationMatrix RotationMatrix(SplineRotation);
	const FVector RightVector = RotationMatrix.GetScaledAxis(EAxis::Y);
	const FVector UpVector = RotationMatrix.GetScaledAxis(EAxis::Z);
	const FVector GhostLocation = SplineLocation + RightVector * LateralOffset + UpVector * RiderZOffset;
	FRotator GhostRotation = bFaceAlongSpline ? SplineRotation : GetActorRotation();
	GhostRotation.Yaw += RiderYawOffset;

	GhostComponent->SetWorldLocationAndRotation(
		GhostLocation,
		GhostRotation,
		false,
		nullptr,
		ETeleportType::None);
	GhostComponent->SetVisibility(Opacity > UE_KINDA_SMALL_NUMBER, true);
}

void APelotonSplineActor::ApplyRiderMaterial(UStaticMeshComponent* RiderMeshComponent) const
{
	if (!RiderMeshComponent || !RiderMaterial)
	{
		return;
	}

	const int32 MaterialSlotCount = GetRiderMaterialSlotCount();
	for (int32 MaterialIndex = 0; MaterialIndex < MaterialSlotCount; ++MaterialIndex)
	{
		RiderMeshComponent->SetMaterial(MaterialIndex, RiderMaterial);
	}
}

void APelotonSplineActor::ApplyGhostMaterial(UStaticMeshComponent* GhostComponent)
{
	if (!GhostComponent || !GhostMaterial)
	{
		return;
	}

	const int32 MaterialSlotCount = GetRiderMaterialSlotCount();
	for (int32 MaterialIndex = 0; MaterialIndex < MaterialSlotCount; ++MaterialIndex)
	{
		if (!Cast<UMaterialInstanceDynamic>(GhostComponent->GetMaterial(MaterialIndex)))
		{
			GhostComponent->CreateAndSetMaterialInstanceDynamicFromMaterial(MaterialIndex, GhostMaterial);
		}
	}
}

void APelotonSplineActor::RefreshGhostMaterials()
{
	auto RefreshGhostArray = [this](
		TArray<TObjectPtr<UStaticMeshComponent>>& GhostComponents,
		const FLinearColor& Color)
	{
		for (int32 GhostIndex = 0; GhostIndex < GhostComponents.Num(); ++GhostIndex)
		{
			const float FadeRatio = GhostComponents.Num() <= 1
				? 0.0f
				: static_cast<float>(GhostIndex) / static_cast<float>(GhostComponents.Num() - 1);
			const float Opacity = GetGhostOpacity(FadeRatio);
			const FLinearColor GhostColor = bUseGhostHeatmap ? GetGhostHeatmapColor(FadeRatio) : Color;
			UpdateGhostMaterialParameters(GhostComponents[GhostIndex], GhostColor, Opacity);
		}
	};

	RefreshGhostArray(ForwardGhostComponents, ForwardGhostColor);
	RefreshGhostArray(BackwardGhostComponents, BackwardGhostColor);
}

void APelotonSplineActor::UpdateGhostMaterialParameters(
	UStaticMeshComponent* GhostComponent,
	const FLinearColor& Color,
	float Opacity)
{
	if (!GhostComponent)
	{
		return;
	}

	ApplyGhostMaterial(GhostComponent);

	const float ClampedOpacity = FMath::Clamp(Opacity, 0.0f, 1.0f);
	const int32 MaterialSlotCount = GetRiderMaterialSlotCount();
	for (int32 MaterialIndex = 0; MaterialIndex < MaterialSlotCount; ++MaterialIndex)
	{
		UMaterialInstanceDynamic* DynamicMaterial = Cast<UMaterialInstanceDynamic>(GhostComponent->GetMaterial(MaterialIndex));
		if (!DynamicMaterial)
		{
			continue;
		}

		DynamicMaterial->SetVectorParameterValue(TEXT("GhostColor"), Color);
		DynamicMaterial->SetScalarParameterValue(TEXT("GhostOpacity"), ClampedOpacity);
	}
}

int32 APelotonSplineActor::GetRiderMaterialSlotCount() const
{
	if (!RiderStaticMesh)
	{
		return 1;
	}

	return FMath::Max(1, RiderStaticMesh->GetStaticMaterials().Num());
}

FVector2D APelotonSplineActor::GetFormationOffset(int32 RiderIndex) const
{
	int32 RemainingIndex = FMath::Max(0, RiderIndex);
	int32 RowIndex = 0;
	int32 RowCapacity = 1;
	const int32 SafeMaxRidersPerRow = FMath::Clamp(MaxRidersPerRow, 1, 8);

	while (RemainingIndex >= RowCapacity)
	{
		RemainingIndex -= RowCapacity;
		++RowIndex;
		RowCapacity = FMath::Min(RowIndex + 1, SafeMaxRidersPerRow);
	}

	const float DistanceBehindLeader = static_cast<float>(RowIndex) * LongitudinalSpacing;
	const float CenteredLane = static_cast<float>(RemainingIndex) - (static_cast<float>(RowCapacity - 1) * 0.5f);
	float LateralOffset = CenteredLane * LateralSpacing;
	if ((RowIndex % 2) == 1)
	{
		LateralOffset += AlternateRowLateralStagger;
	}

	return FVector2D(DistanceBehindLeader, LateralOffset);
}

float APelotonSplineActor::GetGhostOpacity(float FadeRatio) const
{
	const float Alpha = FMath::Clamp(FadeRatio, 0.0f, 1.0f);
	const float MaxOpacity = FMath::Clamp(GhostMaxOpacity, 0.0f, 1.0f);
	const float MinOpacity = FMath::Clamp(GhostMinOpacity, 0.0f, MaxOpacity);
	return FMath::Lerp(MaxOpacity, MinOpacity, Alpha);
}

FLinearColor APelotonSplineActor::GetGhostHeatmapColor(float FadeRatio) const
{
	const float Alpha = FMath::Clamp(FadeRatio, 0.0f, 1.0f);
	if (Alpha <= 0.5f)
	{
		return FMath::Lerp(GhostHotColor, GhostMidColor, Alpha * 2.0f);
	}

	return FMath::Lerp(GhostMidColor, GhostColdColor, (Alpha - 0.5f) * 2.0f);
}

int32 APelotonSplineActor::GetGhostCount(float Distance) const
{
	if (Distance <= UE_KINDA_SMALL_NUMBER || GhostSpacing <= UE_KINDA_SMALL_NUMBER)
	{
		return 0;
	}

	const int32 SafeMaxGhostsPerSide = FMath::Clamp(MaxGhostsPerSide, 0, 32);
	return FMath::Clamp(FMath::CeilToInt(Distance / GhostSpacing), 0, SafeMaxGhostsPerSide);
}

float APelotonSplineActor::NormalizeSplineDistance(float Distance) const
{
	if (!RouteSpline)
	{
		return Distance;
	}

	const float SplineLength = RouteSpline->GetSplineLength();
	if (SplineLength <= UE_KINDA_SMALL_NUMBER)
	{
		return 0.0f;
	}

	if (bLoop || RouteSpline->IsClosedLoop())
	{
		const float WrappedDistance = FMath::Fmod(Distance, SplineLength);
		return WrappedDistance < 0.0f ? WrappedDistance + SplineLength : WrappedDistance;
	}

	return FMath::Clamp(Distance, 0.0f, SplineLength);
}

bool APelotonSplineActor::CanBuildRiderComponents() const
{
	return !HasAnyFlags(RF_ClassDefaultObject | RF_ArchetypeObject) && GetWorld() && SceneRoot;
}
