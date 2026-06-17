#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Math/RandomStream.h"
#include "CowHerdSubsystem.generated.h"

UCLASS()
class AIRTRAFFIC_API UCowHerdSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

private:
	struct FCowAgent
	{
		TWeakObjectPtr<AActor> Actor;
		FVector Center = FVector::ZeroVector;
		FVector2D LocalPos = FVector2D::ZeroVector;
		float HeadingRad = 0.0f;
		float SpeedCmPerSecond = 0.0f;
		bool bMoving = false;
		float TimeRemaining = 0.0f;
		FRandomStream Rng;
	};

	TArray<FCowAgent> Cows;
	float TimeSinceScanS = 1.0e9f;

	void DiscoverCows();
	bool AlreadyTracked(const AActor* Actor) const;
	void StepCow(FCowAgent& Cow, float DeltaTime);
};
