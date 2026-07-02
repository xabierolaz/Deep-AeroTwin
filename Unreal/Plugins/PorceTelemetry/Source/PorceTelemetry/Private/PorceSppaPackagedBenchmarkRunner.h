#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PorceSppaPackagedBenchmarkRunner.generated.h"

class UPorceTelemetryComponent;

UCLASS()
class APorceSppaPackagedBenchmarkRunner : public AActor
{
    GENERATED_BODY()

public:
    APorceSppaPackagedBenchmarkRunner();

    static bool IsBenchmarkRequested();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

private:
    enum class EBenchmarkPhase : uint8
    {
        StartCondition,
        CreateWarmup,
        CreateMeasure,
        PoseWarmup,
        PoseMeasure,
        ShapeWarmup,
        ShapeMeasure,
        FinishCondition,
        Done
    };

    struct FBenchmarkCondition
    {
        FString Backend;
        int32 Count = 0;
        int32 Repetition = 0;
    };

    UPROPERTY()
    TObjectPtr<AActor> TelemetryOwner;

    UPROPERTY()
    TObjectPtr<UPorceTelemetryComponent> TelemetryComponent;

    TArray<FBenchmarkCondition> Conditions;
    int32 ConditionIndex = -1;
    EBenchmarkPhase Phase = EBenchmarkPhase::StartCondition;
    int32 FrameInPhase = 0;
    int32 PoseSequence = 0;
    int32 ShapeSequence = 0;
    bool bStarted = false;
    bool bFinished = false;

    FString OutDir;
    FString FrameRows;
    FString ActionRows;
    FString FailureRows;
    FString ManifestJson;

    TArray<int32> Counts;
    TArray<FString> Backends;
    int32 Repetitions = 1;
    int32 WarmupFrames = 30;
    int32 MeasureFrames = 120;
    int32 UpdateEveryFrames = 15;
    int32 Seed = 20260702;
    int32 ResolutionX = 1280;
    int32 ResolutionY = 720;
    bool bRequestCsvProfile = true;

    void ParseConfig();
    void BuildConditions();
    void SetupScene();
    void StartCondition();
    void FinishCondition();
    void CleanupManagedActors();
    void EnsureTelemetryComponent(const FString& Backend);
    void ApplyActionPayload(const FString& Action, int32 Sequence);
    FString BuildObstaclePayload(const FString& Backend, const FString& Action, int32 Sequence) const;
    TSharedPtr<FJsonObject> BuildObstacleObject(int32 Index, const FString& Action, int32 Sequence) const;
    TSharedPtr<FJsonObject> BuildDescriptorObject(int32 Index) const;
    TSharedPtr<FJsonObject> BuildUpdatePacketObject(int32 Index, const FString& Action, int32 Sequence) const;
    void AddPart(TArray<TSharedPtr<FJsonValue>>& Parts, const FString& PartRole, const FString& Primitive, const FVector& CenterM, const FVector& Scale, const FString& MaterialRole) const;
    FString JsonToString(const TSharedPtr<FJsonObject>& Object) const;
    void RecordFrame(float DeltaSeconds);
    void RecordAction(const FString& Action, double ElapsedMs, bool bOk);
    void CountManagedScene(int32& OutActors, int32& OutStaticMeshComponents, int64& OutTriangles, int64& OutEstimatedDraws) const;
    FString CurrentBackend() const;
    int32 CurrentCount() const;
    int32 CurrentRepetition() const;
    FString PhaseName() const;
    void AdvancePhase();
    void FinishBenchmark();
    void WriteArtifacts();
    void AppendFailure(const FString& Message);
};
