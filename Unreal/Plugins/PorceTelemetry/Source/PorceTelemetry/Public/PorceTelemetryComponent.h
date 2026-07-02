#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "PorceTelemetryComponent.generated.h"

class FJsonValue;
class STextBlock;
class SWidget;

UENUM(BlueprintType)
enum class EPorceTwinSpawnBackend : uint8
{
    UnrealAssets UMETA(DisplayName="Unreal Assets"),
    SemanticProxy UMETA(DisplayName="SPPA Semantic Proxy")
};

struct FPorceTwinEntityState
{
    FString EntityId;
    FString ClassName;
    float LastConfidence = 0.0f;
    bool bConfirmed = false;
    bool bHasYawDeg = false;
    float LastYawDeg = 0.0f;
    double LastSeenTs = 0.0;
    FVector SmoothedWorldLocation = FVector::ZeroVector;
    bool bHasSppaDescriptorJson = false;
    FString LastSppaDescriptorJson;
    bool bHasSppaUpdatePacketJson = false;
    FString LastSppaUpdatePacketJson;
    TWeakObjectPtr<AActor> SpawnedActor;
    TSubclassOf<AActor> SpawnedActorClass;
    EPorceTwinSpawnBackend SpawnedBackend = EPorceTwinSpawnBackend::UnrealAssets;
    bool bCesiumBaseHeightInitialized = false;
    double CesiumBaseHeightM = 0.0;
};

UCLASS(ClassGroup=(PORCEV2), meta=(BlueprintSpawnableComponent, DisplayName="PORCE Twin V2 Component"))
class PORCETELEMETRY_API UPorceTelemetryComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UPorceTelemetryComponent();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2")
    void PollNow();

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2")
    void SendNow();

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|Debug")
    bool ApplyObstacleBatchJson(const FString& PayloadJson);

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|Debug")
    bool PollNowBlockingForTest(float TimeoutS = 2.0f);

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|Spawn")
    void SetSpawnBackend(EPorceTwinSpawnBackend NewBackend);

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|Spawn")
    void ToggleSpawnBackend();

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|Spawn")
    EPorceTwinSpawnBackend GetSpawnBackend() const;

    UFUNCTION(BlueprintCallable, Category="PORCE Twin V2|Spawn")
    bool IsUsingSemanticProxyBackend() const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Endpoint")
    bool bEnabled = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Endpoint")
    FString EndpointUrl = TEXT("http://127.0.0.1:8080/api/ui/data");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Endpoint")
    FString AuthToken;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Endpoint")
    float PollRateHz = 5.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Endpoint")
    float RequestTimeoutS = 0.35f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Lifecycle")
    float DespawnAfterS = 3.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Lifecycle")
    float ConfirmedConfidenceThreshold = 0.65f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Lifecycle")
    float TentativeSmoothingAlpha = 0.20f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Lifecycle")
    float ConfirmedSmoothingAlpha = 0.55f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Lifecycle")
    bool bHideUnconfirmedActors = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Lifecycle")
    float ObstacleZOffsetCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Spawn")
    TSubclassOf<AActor> DefaultObstacleActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Spawn")
    TSubclassOf<AActor> BikerActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Spawn")
    TSubclassOf<AActor> CowActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Spawn")
    TSubclassOf<AActor> TowerActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Spawn")
    EPorceTwinSpawnBackend SpawnBackend = EPorceTwinSpawnBackend::UnrealAssets;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Spawn")
    TSubclassOf<AActor> SemanticProxyActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Spawn")
    bool bShowSpawnBackendSwitchUI = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Debug", AdvancedDisplay)
    bool bBenchmarkDisableActorSpawning = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Frame")
    AActor* OriginActor = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Frame")
    float CmToMScale = 0.01f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Frame")
    float EastFromLocalX = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Frame")
    float EastFromLocalY = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Frame")
    float NorthFromLocalX = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Frame")
    float NorthFromLocalY = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Geodesy")
    double HomeLatDeg = 42.229695;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PORCE Twin V2|Geodesy")
    double HomeLonDeg = -1.235085;

private:
    double LastPollTs = 0.0;
    bool bRequestInFlight = false;
    bool bLastPollSucceededForTest = false;
    TMap<FString, FPorceTwinEntityState> EntityStates;

    bool IsTwinConsumerEnabled() const;
    double ResolvePollPeriodS() const;
    FString ResolveToken() const;
    bool TryNEDToWorldCm(double NorthM, double EastM, double UpM, FVector& OutWorldCm) const;
    bool TryLatLonToWorldCm(double LatDeg, double LonDeg, FVector& OutWorldCm) const;
    TSubclassOf<AActor> ResolveActorClassForType(const FString& RawType) const;
    TSubclassOf<AActor> ResolveActorClassForState(const FPorceTwinEntityState& State) const;
    void StartPollRequest(double NowTs);
    void OnPollResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);
    void ApplyObstacleBatch(const TArray<TSharedPtr<FJsonValue>>& Obstacles, double NowTs);
    void UpsertObstacle(
        const FString& EntityId,
        const FString& ClassName,
        bool bHasLatLon,
        double LatDeg,
        double LonDeg,
        bool bHasWorldNed,
        double WorldNorthM,
        double WorldEastM,
        double WorldUpM,
        bool bHasYawDeg,
        float YawDeg,
        float Confidence,
        const FString& SppaDescriptorJson,
        const FString& SppaUpdatePacketJson,
        double NowTs
    );
    void PruneStaleEntities(double NowTs);
    void DestroyAllSpawnedActors();
    void DestroySpawnedActorForState(FPorceTwinEntityState& State);
    AActor* SpawnActorForState(FPorceTwinEntityState& State);
    void ConfigureSpawnedActor(FPorceTwinEntityState& State);
    void RebuildSpawnedActorsForCurrentBackend();
    void ApplyConfiguredSpawnBackendFromEnvironment();
    void InstallSpawnBackendSwitchUI();
    void RemoveSpawnBackendSwitchUI();
    FText GetSpawnBackendSwitchText() const;

    TSharedPtr<SWidget> SpawnBackendSwitchWidget;
    TSharedPtr<STextBlock> SpawnBackendSwitchText;
};
