#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "PorceTelemetryComponent.generated.h"

class FJsonValue;

struct FPorceTwinEntityState
{
    FString EntityId;
    FString ClassName;
    float LastConfidence = 0.0f;
    bool bConfirmed = false;
    double LastSeenTs = 0.0;
    FVector SmoothedWorldLocation = FVector::ZeroVector;
    TWeakObjectPtr<AActor> SpawnedActor;
};

UCLASS(ClassGroup=(PORCE), meta=(BlueprintSpawnableComponent))
class PORCETELEMETRY_API UPorceTelemetryComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UPorceTelemetryComponent();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

    UFUNCTION(BlueprintCallable, Category="PORCE Twin")
    void PollNow();

    UFUNCTION(BlueprintCallable, Category="PORCE Twin")
    void SendNow();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Endpoint")
    bool bEnabled = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Endpoint")
    FString EndpointUrl = TEXT("http://127.0.0.1:8080/api/ui/data");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Endpoint")
    FString AuthToken;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Endpoint")
    float PollRateHz = 5.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Endpoint")
    float RequestTimeoutS = 0.35f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Lifecycle")
    float DespawnAfterS = 3.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Lifecycle")
    float ConfirmedConfidenceThreshold = 0.65f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Lifecycle")
    float TentativeSmoothingAlpha = 0.20f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Lifecycle")
    float ConfirmedSmoothingAlpha = 0.55f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Lifecycle")
    bool bHideUnconfirmedActors = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Lifecycle")
    float ObstacleZOffsetCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Spawn")
    TSubclassOf<AActor> DefaultObstacleActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Spawn")
    TSubclassOf<AActor> BikerActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Spawn")
    TSubclassOf<AActor> CowActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Spawn")
    TSubclassOf<AActor> TowerActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Frame")
    AActor* OriginActor = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Frame")
    float CmToMScale = 0.01f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Frame")
    float EastFromLocalX = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Frame")
    float EastFromLocalY = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Frame")
    float NorthFromLocalX = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Frame")
    float NorthFromLocalY = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Geodesy")
    double HomeLatDeg = 42.229695;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin|Geodesy")
    double HomeLonDeg = -1.235085;

private:
    double LastPollTs = 0.0;
    bool bRequestInFlight = false;
    TMap<FString, FPorceTwinEntityState> EntityStates;

    bool IsTwinConsumerEnabled() const;
    double ResolvePollPeriodS() const;
    FString ResolveToken() const;
    bool TryLatLonToWorldCm(double LatDeg, double LonDeg, FVector& OutWorldCm) const;
    TSubclassOf<AActor> ResolveActorClassForType(const FString& RawType) const;
    void StartPollRequest(double NowTs);
    void OnPollResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);
    void ApplyObstacleBatch(const TArray<TSharedPtr<FJsonValue>>& Obstacles, double NowTs);
    void UpsertObstacle(
        const FString& EntityId,
        const FString& ClassName,
        double LatDeg,
        double LonDeg,
        float Confidence,
        double NowTs
    );
    void PruneStaleEntities(double NowTs);
    void DestroyAllSpawnedActors();
};
