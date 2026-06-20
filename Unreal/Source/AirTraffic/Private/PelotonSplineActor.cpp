#include "PelotonSplineActor.h"

#include "Components/ActorComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "UObject/ConstructorHelpers.h"

APelotonSplineActor::APelotonSplineActor()
{
	PrimaryActorTick.bCanEverTick = true;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);

	RouteSpline = CreateDefaultSubobject<USplineComponent>(TEXT("RouteSpline"));
	RouteSpline->SetupAttachment(SceneRoot);
	RouteSpline->bEditableWhenInherited = true;
	RouteSpline->SetClosedLoop(false);
	RouteSpline->bDrawDebug = false;
	RouteSpline->ClearSplinePoints(false);
	RouteSpline->AddSplinePoint(FVector(-2400.0f, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
	RouteSpline->AddSplinePoint(FVector(2400.0f, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
	RouteSpline->UpdateSpline();

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> DefaultRiderMesh(
		TEXT("/Game/Peloton/TexturedBiker/biker_text_pedal_loop/SkeletalMeshes/biker_text_pedal_loop"));
	if (DefaultRiderMesh.Succeeded())
	{
		RiderSkeletalMesh = DefaultRiderMesh.Object;
	}
}

void APelotonSplineActor::BeginPlay()
{
	Super::BeginPlay();
	RuntimeLeadDistance = NormalizeSplineDistance(StartDistance);
	DestroyLegacyComponents();
	EnsureRiderComponents();
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
		const bool bSynchronized = UpdateSynchronizedLeadDistance();
		if (!bSynchronized)
		{
			RuntimeLeadDistance = NormalizeSplineDistance(RuntimeLeadDistance + SpeedCmPerSecond * DeltaSeconds);
		}
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
	DestroyLegacyComponents();
	EnsureRiderComponents();
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

void APelotonSplineActor::DestroyRiderSkeletalMeshComponents()
{
	for (USkeletalMeshComponent* RiderMeshComponent : RiderSkeletalMeshComponents)
	{
		if (RiderMeshComponent)
		{
			RiderMeshComponent->DestroyComponent();
		}
	}
	RiderSkeletalMeshComponents.Reset();
}

void APelotonSplineActor::DestroyLegacyComponents()
{
	TArray<UActorComponent*> Components;
	GetComponents(Components);
	for (UActorComponent* Component : Components)
	{
		if (!Component)
		{
			continue;
		}

		const FString ComponentName = Component->GetName();
		if (ComponentName.Contains(TEXT("Ghost"), ESearchCase::IgnoreCase) ||
			ComponentName.Contains(TEXT("RiderMesh"), ESearchCase::IgnoreCase))
		{
			Component->DestroyComponent();
		}
	}
}

void APelotonSplineActor::EnsureRiderComponents()
{
	if (!CanBuildRiderComponents())
	{
		return;
	}

	DestroyLegacyComponents();

	const int32 SafeRiderCount = FMath::Clamp(RiderCount, 1, 64);
	if (RiderSkeletalMesh)
	{
		if (RiderSkeletalMeshComponents.Num() != SafeRiderCount)
		{
			DestroyRiderSkeletalMeshComponents();
			for (int32 RiderIndex = 0; RiderIndex < SafeRiderCount; ++RiderIndex)
			{
				const FName ComponentName(*FString::Printf(TEXT("PelotonRiderSkeletalMesh_%02d"), RiderIndex + 1));
				USkeletalMeshComponent* RiderMeshComponent = NewObject<USkeletalMeshComponent>(this, ComponentName);
				RiderMeshComponent->CreationMethod = EComponentCreationMethod::UserConstructionScript;
				RiderMeshComponent->SetSkeletalMesh(RiderSkeletalMesh);
				ApplyRiderMaterial(RiderMeshComponent);
				RiderMeshComponent->SetMobility(EComponentMobility::Movable);
				RiderMeshComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				RiderMeshComponent->SetCastShadow(bRidersCastShadows);
				RiderMeshComponent->SetReceivesDecals(false);
				RiderMeshComponent->SetComponentTickEnabled(false);
				RiderMeshComponent->SetupAttachment(SceneRoot);
				RiderMeshComponent->RegisterComponent();
				AddInstanceComponent(RiderMeshComponent);
				RiderSkeletalMeshComponents.Add(RiderMeshComponent);
			}
		}

		for (int32 RiderIndex = 0; RiderIndex < RiderSkeletalMeshComponents.Num(); ++RiderIndex)
		{
			USkeletalMeshComponent* RiderMeshComponent = RiderSkeletalMeshComponents[RiderIndex];
			if (!RiderMeshComponent)
			{
				continue;
			}
			if (RiderMeshComponent->GetSkeletalMeshAsset() != RiderSkeletalMesh)
			{
				RiderMeshComponent->SetSkeletalMesh(RiderSkeletalMesh);
			}
			RiderMeshComponent->SetCastShadow(bRidersCastShadows);
			RiderMeshComponent->SetReceivesDecals(false);
			RiderMeshComponent->SetComponentTickEnabled(false);
			ApplyRiderMaterial(RiderMeshComponent);
			UpdatePedalMorph(RiderMeshComponent, RiderIndex);
		}
		return;
	}

	DestroyRiderSkeletalMeshComponents();
}

void APelotonSplineActor::UpdateRiderTransforms(float LeadDistance)
{
	if (!RouteSpline || RiderSkeletalMeshComponents.IsEmpty())
	{
		return;
	}

	const float SplineLength = RouteSpline->GetSplineLength();
	if (SplineLength <= UE_KINDA_SMALL_NUMBER)
	{
		return;
	}

	const int32 ActiveRiderCount = RiderSkeletalMeshComponents.Num();
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

		USkeletalMeshComponent* RiderMeshComponent = RiderSkeletalMeshComponents[RiderIndex];
		if (RiderMeshComponent)
		{
			RiderMeshComponent->SetWorldLocationAndRotation(
				RiderLocation,
				RiderRotation,
				false,
				nullptr,
				ETeleportType::None);
			UpdatePedalMorph(RiderMeshComponent, RiderIndex);
		}
	}
}

void APelotonSplineActor::ApplyRiderMaterial(USkeletalMeshComponent* RiderMeshComponent) const
{
	if (!RiderMeshComponent)
	{
		return;
	}

	const int32 MaterialSlotCount = RiderMeshComponent->GetNumMaterials();
	for (int32 MaterialIndex = 0; MaterialIndex < MaterialSlotCount; ++MaterialIndex)
	{
		if (RiderMaterial)
		{
			RiderMeshComponent->SetMaterial(MaterialIndex, RiderMaterial.Get());
		}
	}
}

void APelotonSplineActor::UpdatePedalMorph(USkeletalMeshComponent* RiderMeshComponent, int32 RiderIndex) const
{
	if (!RiderMeshComponent || !bAnimatePedalMorph || PedalMorphTargetName.IsNone())
	{
		return;
	}

	UWorld* World = GetWorld();
	const float TimeSeconds = World ? World->GetTimeSeconds() : 0.0f;
	const float SafeCycleSeconds = FMath::Max(0.05f, PedalCycleSeconds);
	const float Phase = FMath::Frac((TimeSeconds / SafeCycleSeconds) + static_cast<float>(RiderIndex) * PedalPhaseOffsetPerRider);
	const float SmoothLoop = 0.5f - 0.5f * FMath::Cos(Phase * 2.0f * PI);
	const float MinValue = FMath::Clamp(PedalMorphMin, 0.0f, 1.0f);
	const float MaxValue = FMath::Clamp(PedalMorphMax, 0.0f, 1.0f);
	const float MorphValue = FMath::Lerp(MinValue, MaxValue, SmoothLoop);
	RiderMeshComponent->SetMorphTarget(PedalMorphTargetName, MorphValue, false);
}

AActor* APelotonSplineActor::ResolveSyncTargetActor()
{
	if (!bSyncToTargetActor)
	{
		return nullptr;
	}

	if (CachedSyncTargetActor.IsValid())
	{
		return CachedSyncTargetActor.Get();
	}

	UWorld* World = GetWorld();
	if (!World)
	{
		return nullptr;
	}

	const FString TargetText = SyncTargetActorLabel.TrimStartAndEnd();
	if (TargetText.IsEmpty())
	{
		return nullptr;
	}

	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Candidate = *It;
		if (!Candidate)
		{
			continue;
		}

		const FString CandidateName = Candidate->GetName();
		if (CandidateName.Equals(TargetText, ESearchCase::IgnoreCase) ||
			CandidateName.Contains(TargetText, ESearchCase::IgnoreCase))
		{
			CachedSyncTargetActor = Candidate;
			return Candidate;
		}

#if WITH_EDITOR
		const FString CandidateLabel = Candidate->GetActorLabel();
		if (CandidateLabel.Equals(TargetText, ESearchCase::IgnoreCase) ||
			CandidateLabel.Contains(TargetText, ESearchCase::IgnoreCase))
		{
			CachedSyncTargetActor = Candidate;
			return Candidate;
		}
#endif
	}

	return nullptr;
}

bool APelotonSplineActor::UpdateSynchronizedLeadDistance()
{
	if (!bSyncToTargetActor || !RouteSpline)
	{
		return false;
	}

	UWorld* World = GetWorld();
	FVector TargetLocation = FVector::ZeroVector;
	FString TargetDebugName;
	AActor* TargetActor = nullptr;
	if (bSyncToPlayerCamera && World && World->IsGameWorld())
	{
		if (APlayerController* PlayerController = World->GetFirstPlayerController())
		{
			if (PlayerController->PlayerCameraManager)
			{
				TargetLocation = PlayerController->PlayerCameraManager->GetCameraLocation();
				TargetDebugName = TEXT("PlayerCameraManager");
			}
		}
	}

	if (TargetDebugName.IsEmpty())
	{
		TargetActor = ResolveSyncTargetActor();
		if (!TargetActor)
		{
			return false;
		}
		TargetLocation = TargetActor->GetActorLocation();
#if WITH_EDITOR
		TargetDebugName = TargetActor->GetActorLabel();
#else
		TargetDebugName = TargetActor->GetName();
#endif
	}

	FVector Direction = SyncApproachDirection;
	Direction.Z = 0.0f;
	if (!Direction.Normalize())
	{
		const float ReferenceDistance = SyncCrossingDistance > UE_KINDA_SMALL_NUMBER
			? SyncCrossingDistance
			: EditorPreviewDistance;
		Direction = RouteSpline->GetDirectionAtDistanceAlongSpline(
			NormalizeSplineDistance(ReferenceDistance),
			ESplineCoordinateSpace::World);
		Direction.Z = 0.0f;
		if (!Direction.Normalize())
		{
			Direction = FVector(1.0f, 0.0f, 0.0f);
		}
	}

	const float CrossingDistance = NormalizeSplineDistance(
		SyncCrossingDistance > UE_KINDA_SMALL_NUMBER ? SyncCrossingDistance : EditorPreviewDistance);
	const FVector CrossingLocation = RouteSpline->GetLocationAtDistanceAlongSpline(
		CrossingDistance,
		ESplineCoordinateSpace::World);
	const float SignedDistanceToCrossing = FVector::DotProduct(CrossingLocation - TargetLocation, Direction);
	const float TargetSpeed = FMath::Max(1.0f, SyncTargetSpeedCmPerSecond);
	const float SecondsUntilTargetCrossing = SignedDistanceToCrossing / TargetSpeed;

	const float TimeSeconds = World ? World->GetTimeSeconds() : 0.0f;
	const float AutonomousLoopDistance = SpeedCmPerSecond * TimeSeconds;
	RuntimeLeadDistance = NormalizeSplineDistance(
		CrossingDistance -
		SpeedCmPerSecond * SecondsUntilTargetCrossing +
		SyncPhaseOffset +
		AutonomousLoopDistance);

	if (TimeSeconds - LastSyncDebugLogTimeSeconds >= 30.0f)
	{
		LastSyncDebugLogTimeSeconds = TimeSeconds;
#if WITH_EDITOR
		const FString ActorText = GetActorLabel();
#else
		const FString ActorText = GetName();
#endif
		UE_LOG(LogTemp, Verbose, TEXT("[PelotonSync] %s target=%s signed_cm=%.1f crossing_cm=%.1f lead_cm=%.1f loop_cm=%.1f target_speed_cm_s=%.1f"),
			*ActorText,
			*TargetDebugName,
			SignedDistanceToCrossing,
			CrossingDistance,
			RuntimeLeadDistance,
			AutonomousLoopDistance,
			TargetSpeed);
	}
	return true;
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
