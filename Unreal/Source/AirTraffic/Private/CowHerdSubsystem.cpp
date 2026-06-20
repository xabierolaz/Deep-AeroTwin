#include "CowHerdSubsystem.h"

#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"

namespace
{
	constexpr float MinSpeedCmS = 80.0f;
	constexpr float MaxSpeedCmS = 120.0f;
	constexpr float MinMoveS = 2.0f;
	constexpr float MaxMoveS = 6.0f;
	constexpr float MinPauseS = 4.0f;
	constexpr float MaxPauseS = 12.0f;
	constexpr float MaxTurnDeg = 75.0f;
	constexpr float WanderRadiusCm = 1500.0f;
	constexpr bool bFaceHeading = true;

	bool IsCowActor(const AActor* Actor)
	{
		if (!Actor)
		{
			return false;
		}

		FString Text = Actor->GetName();
		if (const UClass* ActorClass = Actor->GetClass())
		{
			Text += TEXT(" ");
			Text += ActorClass->GetName();
		}
#if WITH_EDITOR
		Text += TEXT(" ");
		Text += Actor->GetActorLabel();
#endif
		return Text.Contains(TEXT("cow"), ESearchCase::IgnoreCase);
	}
}

bool UCowHerdSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UCowHerdSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UCowHerdSubsystem, STATGROUP_Tickables);
}

bool UCowHerdSubsystem::AlreadyTracked(const AActor* Actor) const
{
	for (const FCowAgent& Cow : Cows)
	{
		if (Cow.Actor.Get() == Actor)
		{
			return true;
		}
	}
	return false;
}

void UCowHerdSubsystem::DiscoverCows()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	int32 Added = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (!Actor || AlreadyTracked(Actor))
		{
			continue;
		}
		if (!IsCowActor(Actor))
		{
			continue;
		}

		TArray<USceneComponent*> SceneComponents;
		Actor->GetComponents<USceneComponent>(SceneComponents);
		for (USceneComponent* Component : SceneComponents)
		{
			if (Component && Component->Mobility != EComponentMobility::Movable)
			{
				Component->SetMobility(EComponentMobility::Movable);
			}
		}

		const int32 Index = Cows.Num();
		FCowAgent Cow;
		Cow.Actor = Actor;
		Cow.Center = Actor->GetActorLocation();
		Cow.Rng.Initialize(1337 + Index * 7919);
		Cow.LocalPos = FVector2D::ZeroVector;
		Cow.HeadingRad = Cow.Rng.FRandRange(0.0f, 2.0f * PI);
		Cow.bMoving = Cow.Rng.FRand() < 0.5f;
		Cow.SpeedCmPerSecond = Cow.bMoving ? Cow.Rng.FRandRange(MinSpeedCmS, MaxSpeedCmS) : 0.0f;
		Cow.TimeRemaining = Cow.bMoving ? Cow.Rng.FRandRange(MinMoveS, MaxMoveS) : Cow.Rng.FRandRange(MinPauseS, MaxPauseS);
		Cows.Add(Cow);
		++Added;
	}

	if (Added > 0)
	{
		UE_LOG(LogTemp, Display, TEXT("CowHerdSubsystem: now driving %d cow(s) (+%d new)."),
			Cows.Num(), Added);
	}
}

void UCowHerdSubsystem::StepCow(FCowAgent& Cow, float DeltaTime)
{
	Cow.TimeRemaining -= DeltaTime;
	if (Cow.TimeRemaining <= 0.0f)
	{
		if (Cow.bMoving)
		{
			Cow.bMoving = false;
			Cow.SpeedCmPerSecond = 0.0f;
			Cow.TimeRemaining = Cow.Rng.FRandRange(MinPauseS, MaxPauseS);
		}
		else
		{
			Cow.bMoving = true;
			Cow.SpeedCmPerSecond = Cow.Rng.FRandRange(MinSpeedCmS, MaxSpeedCmS);
			Cow.HeadingRad += FMath::DegreesToRadians(Cow.Rng.FRandRange(-MaxTurnDeg, MaxTurnDeg));
			Cow.TimeRemaining = Cow.Rng.FRandRange(MinMoveS, MaxMoveS);
		}
	}

	if (Cow.bMoving && Cow.SpeedCmPerSecond > 0.0f)
	{
		const FVector2D Dir(FMath::Cos(Cow.HeadingRad), FMath::Sin(Cow.HeadingRad));
		Cow.LocalPos += Dir * (Cow.SpeedCmPerSecond * DeltaTime);

		const float DistFromCenter = Cow.LocalPos.Size();
		if (WanderRadiusCm > 0.0f && DistFromCenter > WanderRadiusCm)
		{
			Cow.LocalPos = Cow.LocalPos.GetSafeNormal() * WanderRadiusCm;
			Cow.HeadingRad = FMath::Atan2(-Cow.LocalPos.Y, -Cow.LocalPos.X) + Cow.Rng.FRandRange(-0.5f, 0.5f);
		}
	}
}

void UCowHerdSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	TimeSinceScanS += DeltaTime;
	if (TimeSinceScanS >= 3.0f)
	{
		TimeSinceScanS = 0.0f;
		DiscoverCows();
	}

	for (FCowAgent& Cow : Cows)
	{
		AActor* Actor = Cow.Actor.Get();
		if (!Actor)
		{
			continue;
		}
		StepCow(Cow, DeltaTime);
		const FVector NewLocation = Cow.Center + FVector(Cow.LocalPos.X, Cow.LocalPos.Y, 0.0f);
		if (bFaceHeading)
		{
			FRotator NewRotation = Actor->GetActorRotation();
			NewRotation.Yaw = FMath::RadiansToDegrees(Cow.HeadingRad);
			Actor->SetActorLocationAndRotation(NewLocation, NewRotation);
		}
		else
		{
			Actor->SetActorLocation(NewLocation);
		}
	}
}
