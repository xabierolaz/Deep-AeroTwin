#include "PorceSppaPackagedBenchmarkRunner.h"

#include "PorceBenchmarkAssetActor.h"
#include "PorceSemanticProxyActor.h"
#include "PorceTelemetryComponent.h"

#include "Camera/CameraActor.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "StaticMeshResources.h"

namespace
{
FString CsvEscape(const FString& Value)
{
    FString Escaped = Value;
    Escaped.ReplaceInline(TEXT("\""), TEXT("\"\""));
    if (Escaped.Contains(TEXT(",")) || Escaped.Contains(TEXT("\"")) || Escaped.Contains(TEXT("\n")) || Escaped.Contains(TEXT("\r")))
    {
        return FString::Printf(TEXT("\"%s\""), *Escaped);
    }
    return Escaped;
}

FString BoolCsv(bool bValue)
{
    return bValue ? TEXT("1") : TEXT("0");
}

TArray<TSharedPtr<FJsonValue>> NumberArray3(const FVector& Value)
{
    TArray<TSharedPtr<FJsonValue>> Values;
    Values.Add(MakeShared<FJsonValueNumber>(Value.X));
    Values.Add(MakeShared<FJsonValueNumber>(Value.Y));
    Values.Add(MakeShared<FJsonValueNumber>(Value.Z));
    return Values;
}

TArray<FString> SplitList(const FString& Raw)
{
    TArray<FString> Parts;
    Raw.ParseIntoArray(Parts, TEXT(","), true);
    for (FString& Part : Parts)
    {
        Part = Part.TrimStartAndEnd().ToLower();
    }
    Parts.RemoveAll([](const FString& Part) { return Part.IsEmpty(); });
    return Parts;
}

bool ReadCommandValue(const TCHAR* Cmd, const TCHAR* KeyWithEquals, FString& OutValue)
{
    const FString CommandLine(Cmd);
    const FString Prefix = FString::Printf(TEXT("-%s"), KeyWithEquals);
    int32 Start = CommandLine.Find(Prefix, ESearchCase::IgnoreCase);
    if (Start == INDEX_NONE)
    {
        return false;
    }

    Start += Prefix.Len();
    if (!CommandLine.IsValidIndex(Start))
    {
        OutValue.Reset();
        return true;
    }

    int32 End = Start;
    if (CommandLine[Start] == TEXT('"'))
    {
        ++Start;
        End = Start;
        while (CommandLine.IsValidIndex(End) && CommandLine[End] != TEXT('"'))
        {
            ++End;
        }
    }
    else
    {
        while (CommandLine.IsValidIndex(End) && !FChar::IsWhitespace(CommandLine[End]))
        {
            ++End;
        }
    }

    OutValue = CommandLine.Mid(Start, End - Start);
    return true;
}

FString LabelForIndex(int32 Index)
{
    static const TCHAR* Labels[] = {
        TEXT("cow"),
        TEXT("biker"),
        TEXT("tree"),
        TEXT("car"),
        TEXT("truck"),
        TEXT("tower"),
        TEXT("unknown_label")
    };
    return Labels[FMath::Abs(Index) % UE_ARRAY_COUNT(Labels)];
}

FString ArchetypeForLabel(const FString& Label)
{
    if (Label == TEXT("cow"))
    {
        return TEXT("quadruped");
    }
    if (Label == TEXT("biker"))
    {
        return TEXT("rider_vehicle");
    }
    if (Label == TEXT("tree"))
    {
        return TEXT("tree_like");
    }
    if (Label == TEXT("car"))
    {
        return TEXT("compact_vehicle");
    }
    if (Label == TEXT("truck"))
    {
        return TEXT("long_vehicle");
    }
    if (Label == TEXT("tower"))
    {
        return TEXT("pole_like");
    }
    return TEXT("generic_obstacle");
}

bool IsKnownLabel(const FString& Label)
{
    return Label != TEXT("unknown_label");
}
}

APorceSppaPackagedBenchmarkRunner::APorceSppaPackagedBenchmarkRunner()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
}

bool APorceSppaPackagedBenchmarkRunner::IsBenchmarkRequested()
{
    return FParse::Param(FCommandLine::Get(), TEXT("PorceSPPAPackagedBenchmark"));
}

void APorceSppaPackagedBenchmarkRunner::BeginPlay()
{
    Super::BeginPlay();

    ParseConfig();
    BuildConditions();
    SetupScene();

    FrameRows = TEXT("backend,count,repetition,phase,sample_type,frame_in_phase,delta_ms,fps,managed_actors,static_mesh_components,estimated_triangles,estimated_draw_calls\n");
    ActionRows = TEXT("backend,count,repetition,action,sequence,payload_bytes,elapsed_ms,ok,managed_actors,static_mesh_components,estimated_triangles,estimated_draw_calls\n");
    FailureRows = TEXT("message\n");

    if (bRequestCsvProfile && GEngine != nullptr && GetWorld() != nullptr)
    {
        GEngine->Exec(GetWorld(), TEXT("csvprofile start"));
    }

    bStarted = true;
    UE_LOG(LogTemp, Display, TEXT("PORCE_SPPA_PACKAGED_BENCHMARK_START out=%s conditions=%d"), *OutDir, Conditions.Num());
}

void APorceSppaPackagedBenchmarkRunner::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    if (!bStarted || bFinished)
    {
        return;
    }

    switch (Phase)
    {
    case EBenchmarkPhase::StartCondition:
        StartCondition();
        break;
    case EBenchmarkPhase::CreateWarmup:
    case EBenchmarkPhase::CreateMeasure:
    case EBenchmarkPhase::PoseWarmup:
    case EBenchmarkPhase::PoseMeasure:
    case EBenchmarkPhase::ShapeWarmup:
    case EBenchmarkPhase::ShapeMeasure:
        if (Phase == EBenchmarkPhase::PoseWarmup || Phase == EBenchmarkPhase::PoseMeasure)
        {
            if (FrameInPhase == 0 || (UpdateEveryFrames > 0 && (FrameInPhase % UpdateEveryFrames) == 0))
            {
                ApplyActionPayload(TEXT("pose_update"), ++PoseSequence);
            }
        }
        else if (Phase == EBenchmarkPhase::ShapeWarmup || Phase == EBenchmarkPhase::ShapeMeasure)
        {
            if (FrameInPhase == 0 || (UpdateEveryFrames > 0 && (FrameInPhase % UpdateEveryFrames) == 0))
            {
                ApplyActionPayload(TEXT("shape_param_update"), ++ShapeSequence);
            }
        }
        RecordFrame(DeltaSeconds);
        ++FrameInPhase;
        if (
            ((Phase == EBenchmarkPhase::CreateWarmup || Phase == EBenchmarkPhase::PoseWarmup || Phase == EBenchmarkPhase::ShapeWarmup) && FrameInPhase >= WarmupFrames)
            || ((Phase == EBenchmarkPhase::CreateMeasure || Phase == EBenchmarkPhase::PoseMeasure || Phase == EBenchmarkPhase::ShapeMeasure) && FrameInPhase >= MeasureFrames)
        )
        {
            AdvancePhase();
        }
        break;
    case EBenchmarkPhase::FinishCondition:
        FinishCondition();
        break;
    case EBenchmarkPhase::Done:
        FinishBenchmark();
        break;
    }
}

void APorceSppaPackagedBenchmarkRunner::ParseConfig()
{
    const TCHAR* Cmd = FCommandLine::Get();

    FString CountsRaw = TEXT("10,50,100");
    ReadCommandValue(Cmd, TEXT("PorceSPPABenchmarkCounts="), CountsRaw);
    Counts.Reset();
    for (const FString& Part : SplitList(CountsRaw))
    {
        Counts.Add(FMath::Max(1, FCString::Atoi(*Part)));
    }
    if (Counts.Num() == 0)
    {
        Counts = {10, 50, 100};
    }

    FString BackendsRaw = TEXT("no_render,unreal_assets,semantic_proxy");
    ReadCommandValue(Cmd, TEXT("PorceSPPABenchmarkBackends="), BackendsRaw);
    Backends = SplitList(BackendsRaw);
    if (Backends.Num() == 0)
    {
        Backends = {TEXT("no_render"), TEXT("unreal_assets"), TEXT("semantic_proxy")};
    }

    FParse::Value(Cmd, TEXT("PorceSPPABenchmarkRepetitions="), Repetitions);
    FParse::Value(Cmd, TEXT("PorceSPPABenchmarkWarmupFrames="), WarmupFrames);
    FParse::Value(Cmd, TEXT("PorceSPPABenchmarkMeasureFrames="), MeasureFrames);
    FParse::Value(Cmd, TEXT("PorceSPPABenchmarkUpdateEveryFrames="), UpdateEveryFrames);
    FParse::Value(Cmd, TEXT("PorceSPPABenchmarkSeed="), Seed);
    FParse::Value(Cmd, TEXT("PorceSPPABenchmarkResX="), ResolutionX);
    FParse::Value(Cmd, TEXT("PorceSPPABenchmarkResY="), ResolutionY);

    Repetitions = FMath::Max(1, Repetitions);
    WarmupFrames = FMath::Max(0, WarmupFrames);
    MeasureFrames = FMath::Max(1, MeasureFrames);
    UpdateEveryFrames = FMath::Max(1, UpdateEveryFrames);

    bRequestCsvProfile = !FParse::Param(Cmd, TEXT("PorceSPPABenchmarkNoCsvProfile"));

    ReadCommandValue(Cmd, TEXT("PorceSPPABenchmarkOutDir="), OutDir);
    if (OutDir.IsEmpty())
    {
        const FString Stamp = FDateTime::UtcNow().ToString(TEXT("%Y%m%dT%H%M%SZ"));
        OutDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("PorceSppaPackagedBenchmark"), Stamp);
    }
    FPaths::NormalizeDirectoryName(OutDir);
    IFileManager::Get().MakeDirectory(*OutDir, true);
}

void APorceSppaPackagedBenchmarkRunner::BuildConditions()
{
    Conditions.Reset();
    for (const FString& Backend : Backends)
    {
        if (Backend != TEXT("no_render") && Backend != TEXT("unreal_assets") && Backend != TEXT("semantic_proxy"))
        {
            AppendFailure(FString::Printf(TEXT("Unsupported backend '%s' ignored"), *Backend));
            continue;
        }
        for (int32 Count : Counts)
        {
            for (int32 Rep = 0; Rep < Repetitions; ++Rep)
            {
                FBenchmarkCondition Condition;
                Condition.Backend = Backend;
                Condition.Count = Count;
                Condition.Repetition = Rep;
                Conditions.Add(Condition);
            }
        }
    }
    if (Conditions.Num() == 0)
    {
        AppendFailure(TEXT("No benchmark conditions were configured."));
        Phase = EBenchmarkPhase::Done;
    }
}

void APorceSppaPackagedBenchmarkRunner::SetupScene()
{
    UWorld* World = GetWorld();
    if (World == nullptr)
    {
        return;
    }

    if (GEngine != nullptr)
    {
        GEngine->Exec(World, *FString::Printf(TEXT("r.SetRes %dx%dw"), ResolutionX, ResolutionY));
        GEngine->Exec(World, TEXT("t.MaxFPS 0"));
        GEngine->Exec(World, TEXT("r.VSync 0"));
    }

    ACameraActor* Camera = World->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FVector(-4500.0f, -8500.0f, 5000.0f), FRotator(-32.0f, 58.0f, 0.0f));
    if (IsValid(Camera))
    {
        Camera->Tags.AddUnique(TEXT("PORCE_SPPA_BENCHMARK_HELPER"));
        if (APlayerController* Controller = UGameplayStatics::GetPlayerController(World, 0))
        {
            Controller->SetViewTarget(Camera);
        }
    }

    ADirectionalLight* Light = World->SpawnActor<ADirectionalLight>(ADirectionalLight::StaticClass(), FVector::ZeroVector, FRotator(-45.0f, -35.0f, 0.0f));
    if (IsValid(Light))
    {
        Light->Tags.AddUnique(TEXT("PORCE_SPPA_BENCHMARK_HELPER"));
    }
}

void APorceSppaPackagedBenchmarkRunner::StartCondition()
{
    ++ConditionIndex;
    if (!Conditions.IsValidIndex(ConditionIndex))
    {
        Phase = EBenchmarkPhase::Done;
        return;
    }

    CleanupManagedActors();
    PoseSequence = 0;
    ShapeSequence = 0;
    EnsureTelemetryComponent(CurrentBackend());
    ApplyActionPayload(TEXT("create"), 0);

    Phase = EBenchmarkPhase::CreateWarmup;
    FrameInPhase = 0;
}

void APorceSppaPackagedBenchmarkRunner::FinishCondition()
{
    CleanupManagedActors();
    Phase = EBenchmarkPhase::StartCondition;
    FrameInPhase = 0;
}

void APorceSppaPackagedBenchmarkRunner::CleanupManagedActors()
{
    UWorld* World = GetWorld();
    if (World == nullptr)
    {
        return;
    }

    TArray<AActor*> ToDestroy;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!IsValid(Actor))
        {
            continue;
        }
        if (
            Actor == TelemetryOwner
            || Actor->Tags.Contains(TEXT("PORCE_TWIN_MANAGED"))
            || Actor->Tags.Contains(TEXT("PORCE_BENCHMARK_PLACEHOLDER_ASSET"))
        )
        {
            ToDestroy.Add(Actor);
        }
    }
    for (AActor* Actor : ToDestroy)
    {
        if (IsValid(Actor))
        {
            Actor->Destroy();
        }
    }
    TelemetryOwner = nullptr;
    TelemetryComponent = nullptr;
}

void APorceSppaPackagedBenchmarkRunner::EnsureTelemetryComponent(const FString& Backend)
{
    UWorld* World = GetWorld();
    if (World == nullptr)
    {
        AppendFailure(TEXT("No world available for telemetry component."));
        return;
    }

    FActorSpawnParameters SpawnParameters;
    SpawnParameters.Name = MakeUniqueObjectName(
        World->GetCurrentLevel(),
        AActor::StaticClass(),
        TEXT("PorceSPPABenchmarkTelemetryOwner")
    );
    SpawnParameters.ObjectFlags |= RF_Transient;

    TelemetryOwner = World->SpawnActor<AActor>(
        AActor::StaticClass(),
        FVector::ZeroVector,
        FRotator::ZeroRotator,
        SpawnParameters
    );
    if (!IsValid(TelemetryOwner))
    {
        AppendFailure(TEXT("Could not spawn telemetry owner."));
        return;
    }
    TelemetryOwner->Tags.AddUnique(TEXT("PORCE_SPPA_BENCHMARK_HELPER"));

    const FName ComponentName = MakeUniqueObjectName(
        TelemetryOwner,
        UPorceTelemetryComponent::StaticClass(),
        TEXT("PackagedBenchmarkTelemetry")
    );
    TelemetryComponent = NewObject<UPorceTelemetryComponent>(TelemetryOwner, ComponentName);
    if (!IsValid(TelemetryComponent))
    {
        AppendFailure(TEXT("Could not create telemetry component."));
        return;
    }

    TelemetryComponent->bEnabled = false;
    TelemetryComponent->bShowSpawnBackendSwitchUI = false;
    TelemetryComponent->DespawnAfterS = 3600.0f;
    TelemetryComponent->ConfirmedConfidenceThreshold = 0.20f;
    TelemetryComponent->TentativeSmoothingAlpha = 1.0f;
    TelemetryComponent->ConfirmedSmoothingAlpha = 1.0f;
    TelemetryComponent->bHideUnconfirmedActors = false;
    TelemetryComponent->DefaultObstacleActorClass = APorceBenchmarkAssetActor::StaticClass();
    TelemetryComponent->BikerActorClass = APorceBenchmarkAssetActor::StaticClass();
    TelemetryComponent->CowActorClass = APorceBenchmarkAssetActor::StaticClass();
    TelemetryComponent->TowerActorClass = APorceBenchmarkAssetActor::StaticClass();
    TelemetryComponent->SemanticProxyActorClass = APorceSemanticProxyActor::StaticClass();
    TelemetryComponent->bBenchmarkDisableActorSpawning = Backend == TEXT("no_render");
    TelemetryComponent->SpawnBackend = Backend == TEXT("semantic_proxy")
        ? EPorceTwinSpawnBackend::SemanticProxy
        : EPorceTwinSpawnBackend::UnrealAssets;
    TelemetryOwner->AddInstanceComponent(TelemetryComponent);
    TelemetryComponent->RegisterComponent();
}

void APorceSppaPackagedBenchmarkRunner::ApplyActionPayload(const FString& Action, int32 Sequence)
{
    if (!IsValid(TelemetryComponent))
    {
        AppendFailure(TEXT("Telemetry component is invalid while applying payload."));
        return;
    }

    const FString Payload = BuildObstaclePayload(CurrentBackend(), Action, Sequence);
    const double Start = FPlatformTime::Seconds();
    const bool bOk = TelemetryComponent->ApplyObstacleBatchJson(Payload);
    const double ElapsedMs = (FPlatformTime::Seconds() - Start) * 1000.0;
    RecordAction(Action, ElapsedMs, bOk);
    if (!bOk)
    {
        AppendFailure(FString::Printf(TEXT("ApplyObstacleBatchJson failed backend=%s count=%d rep=%d action=%s"), *CurrentBackend(), CurrentCount(), CurrentRepetition(), *Action));
    }
}

FString APorceSppaPackagedBenchmarkRunner::BuildObstaclePayload(const FString& Backend, const FString& Action, int32 Sequence) const
{
    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    TArray<TSharedPtr<FJsonValue>> Obstacles;
    const int32 Count = CurrentCount();
    Obstacles.Reserve(Count);
    for (int32 Index = 0; Index < Count; ++Index)
    {
        Obstacles.Add(MakeShared<FJsonValueObject>(BuildObstacleObject(Index, Action, Sequence)));
    }
    Root->SetArrayField(TEXT("obstacles"), Obstacles);
    Root->SetStringField(TEXT("benchmark_backend"), Backend);
    Root->SetStringField(TEXT("benchmark_action"), Action);
    Root->SetNumberField(TEXT("benchmark_sequence"), Sequence);
    return JsonToString(Root);
}

TSharedPtr<FJsonObject> APorceSppaPackagedBenchmarkRunner::BuildObstacleObject(int32 Index, const FString& Action, int32 Sequence) const
{
    const int32 Count = FMath::Max(1, CurrentCount());
    const int32 Columns = FMath::CeilToInt(FMath::Sqrt(static_cast<float>(Count)));
    const int32 Row = Index / Columns;
    const int32 Col = Index % Columns;
    const double CenterOffset = (Columns - 1) * 0.5;
    const double SpacingM = 4.0;
    const double NorthM = (Row - CenterOffset) * SpacingM + (Action == TEXT("pose_update") ? Sequence * 0.08 : 0.0);
    const double EastM = (Col - CenterOffset) * SpacingM + (Action == TEXT("pose_update") ? FMath::Sin((Index + Sequence) * 0.37) * 0.18 : 0.0);

    const FString Label = LabelForIndex(Index);
    TSharedPtr<FJsonObject> Obstacle = MakeShared<FJsonObject>();
    Obstacle->SetStringField(TEXT("entity_id"), FString::Printf(TEXT("packaged_%05d"), Index));
    Obstacle->SetStringField(TEXT("object_type"), Label);
    Obstacle->SetNumberField(TEXT("confidence"), IsKnownLabel(Label) ? 0.86 : 0.42);
    Obstacle->SetNumberField(TEXT("yaw_deg"), FMath::Fmod(Index * 17.0 + Sequence * 4.0, 360.0));

    TSharedPtr<FJsonObject> WorldM = MakeShared<FJsonObject>();
    WorldM->SetNumberField(TEXT("north"), NorthM);
    WorldM->SetNumberField(TEXT("east"), EastM);
    WorldM->SetNumberField(TEXT("up"), 0.0);
    Obstacle->SetObjectField(TEXT("world_m"), WorldM);

    if (CurrentBackend() == TEXT("semantic_proxy"))
    {
        if (Action == TEXT("create"))
        {
            Obstacle->SetStringField(TEXT("sppa_descriptor_json"), JsonToString(BuildDescriptorObject(Index)));
        }
        else
        {
            Obstacle->SetStringField(TEXT("sppa_update_packet_json"), JsonToString(BuildUpdatePacketObject(Index, Action, Sequence)));
        }
    }

    return Obstacle;
}

TSharedPtr<FJsonObject> APorceSppaPackagedBenchmarkRunner::BuildDescriptorObject(int32 Index) const
{
    const FString Label = LabelForIndex(Index);
    const FString Archetype = ArchetypeForLabel(Label);
    const bool bKnown = IsKnownLabel(Label);
    const bool bVehicle = Label == TEXT("car") || Label == TEXT("truck");
    const bool bTruck = Label == TEXT("truck");

    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("descriptor_schema"), TEXT("SPPA-DESC-0.2"));
    Root->SetStringField(TEXT("descriptor_id"), FString::Printf(TEXT("packaged-desc-%05d"), Index));
    Root->SetStringField(TEXT("action"), TEXT("create"));

    TSharedPtr<FJsonObject> Input = MakeShared<FJsonObject>();
    Input->SetStringField(TEXT("raw_label"), Label);
    Input->SetStringField(TEXT("normalized_label"), Label);
    Input->SetNumberField(TEXT("confidence"), bKnown ? 0.86 : 0.42);
    Root->SetObjectField(TEXT("input"), Input);

    TSharedPtr<FJsonObject> Semantic = MakeShared<FJsonObject>();
    Semantic->SetStringField(TEXT("normalized_label"), Label);
    Semantic->SetStringField(TEXT("archetype"), Archetype);
    Semantic->SetStringField(TEXT("match_type"), bKnown ? TEXT("exact") : TEXT("fallback_unknown"));
    Semantic->SetBoolField(TEXT("unknown_label"), !bKnown);
    Semantic->SetNumberField(TEXT("class_confidence"), bKnown ? 0.86 : 0.42);
    Root->SetObjectField(TEXT("semantic"), Semantic);

    TSharedPtr<FJsonObject> Resolver = MakeShared<FJsonObject>();
    Resolver->SetStringField(TEXT("input_label"), Label);
    Resolver->SetStringField(TEXT("normalized_label"), Label);
    Resolver->SetStringField(TEXT("resolver_source"), TEXT("packaged_benchmark_static"));
    Resolver->SetStringField(TEXT("archetype_id"), Archetype);
    Resolver->SetStringField(TEXT("match_type"), bKnown ? TEXT("exact") : TEXT("fallback_unknown"));
    Resolver->SetStringField(TEXT("ontology_version"), TEXT("packaged-bench-0.1"));
    Resolver->SetBoolField(TEXT("runtime_llm_used"), false);
    if (!bKnown)
    {
        Resolver->SetStringField(TEXT("fallback_reason"), TEXT("unsupported_benchmark_label"));
    }
    Root->SetObjectField(TEXT("resolver"), Resolver);

    TSharedPtr<FJsonObject> Uncertainty = MakeShared<FJsonObject>();
    Uncertainty->SetBoolField(TEXT("yaw_ambiguous"), true);
    Uncertainty->SetBoolField(TEXT("fallback_unknown"), !bKnown);
    Uncertainty->SetBoolField(TEXT("scale_from_dims"), bVehicle);
    Uncertainty->SetBoolField(TEXT("scale_from_bbox"), !bVehicle);
    Uncertainty->SetStringField(TEXT("shape_source"), bVehicle ? TEXT("metric_dims_input") : TEXT("template_prior"));
    Uncertainty->SetStringField(TEXT("material_source"), bKnown ? TEXT("semantic_prior") : TEXT("fallback_unknown"));
    Root->SetObjectField(TEXT("uncertainty"), Uncertainty);

    const double Length = bTruck ? 5.8 : (Label == TEXT("car") ? 4.2 : 2.0);
    const double Width = bVehicle ? 2.1 : 1.0;
    const double Height = bTruck ? 2.5 : (Label == TEXT("tower") ? 6.0 : 1.6);
    TSharedPtr<FJsonObject> Scale = MakeShared<FJsonObject>();
    Scale->SetStringField(TEXT("scale_source"), bVehicle ? TEXT("metric_dims_input") : TEXT("template_prior"));
    TSharedPtr<FJsonObject> Dims = MakeShared<FJsonObject>();
    Dims->SetNumberField(TEXT("length"), Length);
    Dims->SetNumberField(TEXT("width"), Width);
    Dims->SetNumberField(TEXT("height"), Height);
    Scale->SetObjectField(TEXT("dims_m"), Dims);
    Root->SetObjectField(TEXT("scale"), Scale);

    TArray<TSharedPtr<FJsonValue>> Parts;
    if (!bKnown)
    {
        AddPart(Parts, TEXT("unknown_volume"), TEXT("box"), FVector(0.0f, 0.0f, 0.75f), FVector(2.4f, 1.4f, 1.5f), TEXT("unknown_conservative_volume"));
        AddPart(Parts, TEXT("unknown_footprint"), TEXT("box"), FVector(0.0f, 0.0f, 0.03f), FVector(2.8f, 1.8f, 0.06f), TEXT("unknown_footprint"));
    }
    else if (bVehicle)
    {
        if (bTruck)
        {
            const float CabLength = FMath::Clamp(static_cast<float>(Width * 0.72), 1.45f, 1.85f);
            const float CargoLength = FMath::Max(0.8f, static_cast<float>(Length) - CabLength - 0.55f);
            const float CargoCenterX = static_cast<float>(-Length * 0.5 + 0.25 + CargoLength * 0.5);
            const float CabCenterX = static_cast<float>(Length * 0.5 - 0.25 - CabLength * 0.5);
            AddPart(Parts, TEXT("truck_cargo"), TEXT("box"), FVector(CargoCenterX, 0.0f, 1.35f), FVector(CargoLength, static_cast<float>(Width * 0.92), 1.35f), TEXT("vehicle_body"));
            AddPart(Parts, TEXT("truck_cab"), TEXT("box"), FVector(CabCenterX, 0.0f, 1.2f), FVector(CabLength, static_cast<float>(Width * 0.90), 1.45f), TEXT("vehicle_cab"));
            AddPart(Parts, TEXT("truck_wheel_front_l"), TEXT("cylinder"), FVector(CabCenterX, static_cast<float>(Width * 0.48), 0.42f), FVector(0.34f, 0.34f, 0.16f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("truck_wheel_front_r"), TEXT("cylinder"), FVector(CabCenterX, static_cast<float>(-Width * 0.48), 0.42f), FVector(0.34f, 0.34f, 0.16f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("truck_wheel_rear_l"), TEXT("cylinder"), FVector(CargoCenterX - CargoLength * 0.32f, static_cast<float>(Width * 0.48), 0.42f), FVector(0.34f, 0.34f, 0.16f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("truck_wheel_rear_r"), TEXT("cylinder"), FVector(CargoCenterX - CargoLength * 0.32f, static_cast<float>(-Width * 0.48), 0.42f), FVector(0.34f, 0.34f, 0.16f), TEXT("vehicle_tire"));
        }
        else
        {
            const float CabLength = FMath::Clamp(static_cast<float>(Width * 0.70), 1.05f, 1.42f);
            AddPart(Parts, TEXT("car_body"), TEXT("box"), FVector(0.0f, 0.0f, 0.78f), FVector(static_cast<float>(Length - 0.2), static_cast<float>(Width - 0.12), 0.55f), TEXT("vehicle_body"));
            AddPart(Parts, TEXT("car_cab"), TEXT("box"), FVector(static_cast<float>(-Length * 0.05), 0.0f, 1.18f), FVector(CabLength, static_cast<float>(Width * 0.72), 0.48f), TEXT("vehicle_cab"));
            AddPart(Parts, TEXT("car_wheel_fl"), TEXT("cylinder"), FVector(static_cast<float>(Length * 0.30), static_cast<float>(Width * 0.46), 0.42f), FVector(0.26f, 0.26f, 0.12f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("car_wheel_fr"), TEXT("cylinder"), FVector(static_cast<float>(Length * 0.30), static_cast<float>(-Width * 0.46), 0.42f), FVector(0.26f, 0.26f, 0.12f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("car_wheel_rl"), TEXT("cylinder"), FVector(static_cast<float>(-Length * 0.30), static_cast<float>(Width * 0.46), 0.42f), FVector(0.26f, 0.26f, 0.12f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("car_wheel_rr"), TEXT("cylinder"), FVector(static_cast<float>(-Length * 0.30), static_cast<float>(-Width * 0.46), 0.42f), FVector(0.26f, 0.26f, 0.12f), TEXT("vehicle_tire"));
        }
    }
    else if (Label == TEXT("cow") || Label == TEXT("biker"))
    {
        AddPart(Parts, TEXT("body"), TEXT("sphere"), FVector(0.0f, 0.0f, 1.0f), FVector(0.8f, 0.35f, 0.45f), TEXT("animal_body"));
        AddPart(Parts, TEXT("head"), TEXT("sphere"), FVector(0.85f, 0.0f, 1.25f), FVector(0.25f, 0.20f, 0.22f), TEXT("animal_body"));
        AddPart(Parts, TEXT("leg_fl"), TEXT("cylinder"), FVector(0.42f, 0.24f, 0.45f), FVector(0.08f, 0.08f, 0.75f), TEXT("animal_limb"));
        AddPart(Parts, TEXT("leg_fr"), TEXT("cylinder"), FVector(0.42f, -0.24f, 0.45f), FVector(0.08f, 0.08f, 0.75f), TEXT("animal_limb"));
        AddPart(Parts, TEXT("leg_rl"), TEXT("cylinder"), FVector(-0.42f, 0.24f, 0.45f), FVector(0.08f, 0.08f, 0.75f), TEXT("animal_limb"));
        AddPart(Parts, TEXT("leg_rr"), TEXT("cylinder"), FVector(-0.42f, -0.24f, 0.45f), FVector(0.08f, 0.08f, 0.75f), TEXT("animal_limb"));
    }
    else if (Label == TEXT("tree"))
    {
        AddPart(Parts, TEXT("trunk"), TEXT("cylinder"), FVector(0.0f, 0.0f, 1.2f), FVector(0.18f, 0.18f, 2.4f), TEXT("vegetation_trunk"));
        AddPart(Parts, TEXT("canopy"), TEXT("sphere"), FVector(0.0f, 0.0f, 2.8f), FVector(0.9f, 0.9f, 0.8f), TEXT("vegetation_canopy"));
    }
    else
    {
        AddPart(Parts, TEXT("tower_shaft"), TEXT("cylinder"), FVector(0.0f, 0.0f, 2.8f), FVector(0.15f, 0.15f, 5.6f), TEXT("vertical_structure_metal"));
        AddPart(Parts, TEXT("tower_base"), TEXT("box"), FVector(0.0f, 0.0f, 0.15f), FVector(0.8f, 0.8f, 0.3f), TEXT("vertical_structure_metal"));
    }
    Root->SetArrayField(TEXT("parts"), Parts);
    return Root;
}

TSharedPtr<FJsonObject> APorceSppaPackagedBenchmarkRunner::BuildUpdatePacketObject(int32 Index, const FString& Action, int32 Sequence) const
{
    const FString Label = LabelForIndex(Index);
    const FString Archetype = ArchetypeForLabel(Label);
    const bool bKnown = IsKnownLabel(Label);
    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("packet_schema"), TEXT("SPPA-UPD-0.2"));
    Root->SetStringField(TEXT("descriptor_id"), FString::Printf(TEXT("packaged-desc-%05d"), Index));
    Root->SetStringField(TEXT("action"), Action);

    TSharedPtr<FJsonObject> Semantic = MakeShared<FJsonObject>();
    Semantic->SetStringField(TEXT("normalized_label"), Label);
    Semantic->SetStringField(TEXT("archetype"), Archetype);
    Semantic->SetStringField(TEXT("match_type"), bKnown ? TEXT("exact") : TEXT("fallback_unknown"));
    Semantic->SetBoolField(TEXT("unknown_label"), !bKnown);
    Root->SetObjectField(TEXT("semantic"), Semantic);

    TSharedPtr<FJsonObject> Resolver = MakeShared<FJsonObject>();
    Resolver->SetStringField(TEXT("resolver_source"), TEXT("packaged_benchmark_static"));
    Resolver->SetStringField(TEXT("archetype_id"), Archetype);
    Resolver->SetStringField(TEXT("match_type"), bKnown ? TEXT("exact") : TEXT("fallback_unknown"));
    Resolver->SetBoolField(TEXT("runtime_llm_used"), false);
    Root->SetObjectField(TEXT("resolver"), Resolver);

    TSharedPtr<FJsonObject> Uncertainty = MakeShared<FJsonObject>();
    Uncertainty->SetBoolField(TEXT("yaw_ambiguous"), true);
    Uncertainty->SetBoolField(TEXT("fallback_unknown"), !bKnown);
    Uncertainty->SetBoolField(TEXT("scale_from_dims"), Action == TEXT("shape_param_update"));
    Uncertainty->SetBoolField(TEXT("scale_from_bbox"), Action != TEXT("shape_param_update"));
    Uncertainty->SetStringField(TEXT("material_source"), bKnown ? TEXT("semantic_prior") : TEXT("fallback_unknown"));
    Root->SetObjectField(TEXT("uncertainty"), Uncertainty);

    TSharedPtr<FJsonObject> Scale = MakeShared<FJsonObject>();
    Scale->SetStringField(TEXT("scale_source"), Action == TEXT("shape_param_update") ? TEXT("metric_dims_input") : TEXT("template_prior"));
    TSharedPtr<FJsonObject> Dims = MakeShared<FJsonObject>();
    const double Growth = 1.0 + 0.002 * static_cast<double>(Sequence % 20);
    const double Length = (Label == TEXT("truck") ? 5.8 : 3.0) * Growth;
    const double Width = (Label == TEXT("truck") ? 2.1 : 1.2) * Growth;
    const double Height = (Label == TEXT("tower") ? 6.0 : 1.6) * Growth;
    Dims->SetNumberField(TEXT("length"), Length);
    Dims->SetNumberField(TEXT("width"), Width);
    Dims->SetNumberField(TEXT("height"), Height);
    Scale->SetObjectField(TEXT("dims_m"), Dims);
    Root->SetObjectField(TEXT("scale"), Scale);

    TSharedPtr<FJsonObject> Pose = MakeShared<FJsonObject>();
    Pose->SetBoolField(TEXT("yaw_ambiguous"), true);
    Root->SetObjectField(TEXT("pose"), Pose);

    if (Action == TEXT("shape_param_update"))
    {
        TArray<TSharedPtr<FJsonValue>> Parts;
        if (Label == TEXT("truck"))
        {
            const float CabLength = FMath::Clamp(static_cast<float>(Width * 0.72), 1.45f, 1.85f);
            const float TireRadius = 0.34f;
            const float CargoLength = FMath::Max(0.8f, static_cast<float>(Length) - CabLength - 0.55f);
            const float CargoCenterX = static_cast<float>(-Length * 0.5 + 0.25 + CargoLength * 0.5);
            const float CabCenterX = static_cast<float>(Length * 0.5 - 0.25 - CabLength * 0.5);
            AddPart(Parts, TEXT("truck_cargo"), TEXT("box"), FVector(CargoCenterX, 0.0f, 1.35f), FVector(CargoLength, static_cast<float>(Width * 0.92), 1.35f), TEXT("vehicle_body"));
            AddPart(Parts, TEXT("truck_cab"), TEXT("box"), FVector(CabCenterX, 0.0f, 1.2f), FVector(CabLength, static_cast<float>(Width * 0.90), 1.45f), TEXT("vehicle_cab"));
            AddPart(Parts, TEXT("truck_wheel_front_l"), TEXT("cylinder"), FVector(CabCenterX, static_cast<float>(Width * 0.48), 0.42f), FVector(TireRadius, TireRadius, 0.16f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("truck_wheel_front_r"), TEXT("cylinder"), FVector(CabCenterX, static_cast<float>(-Width * 0.48), 0.42f), FVector(TireRadius, TireRadius, 0.16f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("truck_wheel_rear_l"), TEXT("cylinder"), FVector(CargoCenterX - CargoLength * 0.32f, static_cast<float>(Width * 0.48), 0.42f), FVector(TireRadius, TireRadius, 0.16f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("truck_wheel_rear_r"), TEXT("cylinder"), FVector(CargoCenterX - CargoLength * 0.32f, static_cast<float>(-Width * 0.48), 0.42f), FVector(TireRadius, TireRadius, 0.16f), TEXT("vehicle_tire"));
        }
        else if (Label == TEXT("car"))
        {
            const float TireRadius = 0.26f;
            const float CabLength = FMath::Clamp(static_cast<float>(Width * 0.70), 1.05f, 1.42f);
            AddPart(Parts, TEXT("car_body"), TEXT("box"), FVector(0.0f, 0.0f, 0.78f), FVector(static_cast<float>(Length - 0.2), static_cast<float>(Width - 0.12), 0.55f), TEXT("vehicle_body"));
            AddPart(Parts, TEXT("car_cab"), TEXT("box"), FVector(static_cast<float>(-Length * 0.05), 0.0f, 1.18f), FVector(CabLength, static_cast<float>(Width * 0.72), 0.48f), TEXT("vehicle_cab"));
            AddPart(Parts, TEXT("car_wheel_fl"), TEXT("cylinder"), FVector(static_cast<float>(Length * 0.30), static_cast<float>(Width * 0.46), 0.42f), FVector(TireRadius, TireRadius, 0.12f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("car_wheel_fr"), TEXT("cylinder"), FVector(static_cast<float>(Length * 0.30), static_cast<float>(-Width * 0.46), 0.42f), FVector(TireRadius, TireRadius, 0.12f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("car_wheel_rl"), TEXT("cylinder"), FVector(static_cast<float>(-Length * 0.30), static_cast<float>(Width * 0.46), 0.42f), FVector(TireRadius, TireRadius, 0.12f), TEXT("vehicle_tire"));
            AddPart(Parts, TEXT("car_wheel_rr"), TEXT("cylinder"), FVector(static_cast<float>(-Length * 0.30), static_cast<float>(-Width * 0.46), 0.42f), FVector(TireRadius, TireRadius, 0.12f), TEXT("vehicle_tire"));
        }
        else
        {
            const TSharedPtr<FJsonObject> Descriptor = BuildDescriptorObject(Index);
            const TArray<TSharedPtr<FJsonValue>>* DescriptorParts = nullptr;
            if (Descriptor.IsValid() && Descriptor->TryGetArrayField(TEXT("parts"), DescriptorParts) && DescriptorParts != nullptr)
            {
                Parts = *DescriptorParts;
            }
        }
        Root->SetArrayField(TEXT("parts"), Parts);
    }
    return Root;
}

void APorceSppaPackagedBenchmarkRunner::AddPart(TArray<TSharedPtr<FJsonValue>>& Parts, const FString& PartRole, const FString& Primitive, const FVector& CenterM, const FVector& Scale, const FString& MaterialRole) const
{
    TSharedPtr<FJsonObject> Part = MakeShared<FJsonObject>();
    Part->SetStringField(TEXT("role"), PartRole);
    Part->SetStringField(TEXT("primitive"), Primitive);
    Part->SetStringField(TEXT("material_role"), MaterialRole);
    Part->SetStringField(TEXT("evidence_source"), MaterialRole.Contains(TEXT("unknown")) ? TEXT("fallback_unknown") : TEXT("semantic_prior"));
    Part->SetArrayField(TEXT("scale"), NumberArray3(Scale));
    TSharedPtr<FJsonObject> Pose = MakeShared<FJsonObject>();
    Pose->SetArrayField(TEXT("center"), NumberArray3(CenterM));
    Pose->SetStringField(TEXT("axis"), TEXT("z"));
    Part->SetObjectField(TEXT("local_pose"), Pose);
    Parts.Add(MakeShared<FJsonValueObject>(Part));
}

FString APorceSppaPackagedBenchmarkRunner::JsonToString(const TSharedPtr<FJsonObject>& Object) const
{
    FString Output;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Output);
    FJsonSerializer::Serialize(Object.ToSharedRef(), Writer);
    return Output;
}

void APorceSppaPackagedBenchmarkRunner::RecordFrame(float DeltaSeconds)
{
    int32 ManagedActors = 0;
    int32 StaticMeshComponents = 0;
    int64 Triangles = 0;
    int64 EstimatedDraws = 0;
    CountManagedScene(ManagedActors, StaticMeshComponents, Triangles, EstimatedDraws);

    const bool bWarmup =
        Phase == EBenchmarkPhase::CreateWarmup
        || Phase == EBenchmarkPhase::PoseWarmup
        || Phase == EBenchmarkPhase::ShapeWarmup;
    const float SafeDelta = FMath::Max(DeltaSeconds, KINDA_SMALL_NUMBER);
    FrameRows += FString::Printf(
        TEXT("%s,%d,%d,%s,%s,%d,%.6f,%.6f,%d,%d,%lld,%lld\n"),
        *CsvEscape(CurrentBackend()),
        CurrentCount(),
        CurrentRepetition(),
        *CsvEscape(PhaseName()),
        bWarmup ? TEXT("warmup") : TEXT("measure"),
        FrameInPhase,
        static_cast<double>(SafeDelta * 1000.0f),
        static_cast<double>(1.0f / SafeDelta),
        ManagedActors,
        StaticMeshComponents,
        Triangles,
        EstimatedDraws
    );
}

void APorceSppaPackagedBenchmarkRunner::RecordAction(const FString& Action, double ElapsedMs, bool bOk)
{
    int32 ManagedActors = 0;
    int32 StaticMeshComponents = 0;
    int64 Triangles = 0;
    int64 EstimatedDraws = 0;
    CountManagedScene(ManagedActors, StaticMeshComponents, Triangles, EstimatedDraws);
    const FString Payload = BuildObstaclePayload(CurrentBackend(), Action, Action == TEXT("create") ? 0 : (Action == TEXT("pose_update") ? PoseSequence : ShapeSequence));
    ActionRows += FString::Printf(
        TEXT("%s,%d,%d,%s,%d,%d,%.6f,%s,%d,%d,%lld,%lld\n"),
        *CsvEscape(CurrentBackend()),
        CurrentCount(),
        CurrentRepetition(),
        *CsvEscape(Action),
        Action == TEXT("create") ? 0 : (Action == TEXT("pose_update") ? PoseSequence : ShapeSequence),
        Payload.Len(),
        ElapsedMs,
        *BoolCsv(bOk),
        ManagedActors,
        StaticMeshComponents,
        Triangles,
        EstimatedDraws
    );
}

void APorceSppaPackagedBenchmarkRunner::CountManagedScene(int32& OutActors, int32& OutStaticMeshComponents, int64& OutTriangles, int64& OutEstimatedDraws) const
{
    OutActors = 0;
    OutStaticMeshComponents = 0;
    OutTriangles = 0;
    OutEstimatedDraws = 0;
    const UWorld* World = GetWorld();
    if (World == nullptr)
    {
        return;
    }

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        const AActor* Actor = *It;
        if (!IsValid(Actor) || !Actor->Tags.Contains(TEXT("PORCE_TWIN_MANAGED")))
        {
            continue;
        }
        ++OutActors;
        TArray<UStaticMeshComponent*> Components;
        Actor->GetComponents<UStaticMeshComponent>(Components);
        for (const UStaticMeshComponent* Component : Components)
        {
            if (!IsValid(Component) || !IsValid(Component->GetStaticMesh()))
            {
                continue;
            }
            ++OutStaticMeshComponents;
            const UStaticMesh* Mesh = Component->GetStaticMesh();
            const FStaticMeshRenderData* RenderData = Mesh->GetRenderData();
            if (RenderData != nullptr && RenderData->LODResources.Num() > 0)
            {
                const FStaticMeshLODResources& LOD = RenderData->LODResources[0];
                OutTriangles += LOD.GetNumTriangles();
                OutEstimatedDraws += FMath::Max(1, LOD.Sections.Num());
            }
            else
            {
                ++OutEstimatedDraws;
            }
        }
    }
}

FString APorceSppaPackagedBenchmarkRunner::CurrentBackend() const
{
    return Conditions.IsValidIndex(ConditionIndex) ? Conditions[ConditionIndex].Backend : TEXT("none");
}

int32 APorceSppaPackagedBenchmarkRunner::CurrentCount() const
{
    return Conditions.IsValidIndex(ConditionIndex) ? Conditions[ConditionIndex].Count : 0;
}

int32 APorceSppaPackagedBenchmarkRunner::CurrentRepetition() const
{
    return Conditions.IsValidIndex(ConditionIndex) ? Conditions[ConditionIndex].Repetition : 0;
}

FString APorceSppaPackagedBenchmarkRunner::PhaseName() const
{
    switch (Phase)
    {
    case EBenchmarkPhase::CreateWarmup:
    case EBenchmarkPhase::CreateMeasure:
        return TEXT("create_steady");
    case EBenchmarkPhase::PoseWarmup:
    case EBenchmarkPhase::PoseMeasure:
        return TEXT("pose_stream");
    case EBenchmarkPhase::ShapeWarmup:
    case EBenchmarkPhase::ShapeMeasure:
        return TEXT("shape_stream");
    default:
        return TEXT("setup");
    }
}

void APorceSppaPackagedBenchmarkRunner::AdvancePhase()
{
    FrameInPhase = 0;
    switch (Phase)
    {
    case EBenchmarkPhase::CreateWarmup:
        Phase = EBenchmarkPhase::CreateMeasure;
        break;
    case EBenchmarkPhase::CreateMeasure:
        Phase = EBenchmarkPhase::PoseWarmup;
        break;
    case EBenchmarkPhase::PoseWarmup:
        Phase = EBenchmarkPhase::PoseMeasure;
        break;
    case EBenchmarkPhase::PoseMeasure:
        Phase = EBenchmarkPhase::ShapeWarmup;
        break;
    case EBenchmarkPhase::ShapeWarmup:
        Phase = EBenchmarkPhase::ShapeMeasure;
        break;
    case EBenchmarkPhase::ShapeMeasure:
        Phase = EBenchmarkPhase::FinishCondition;
        break;
    default:
        break;
    }
}

void APorceSppaPackagedBenchmarkRunner::FinishBenchmark()
{
    if (bFinished)
    {
        return;
    }
    bFinished = true;
    CleanupManagedActors();
    if (bRequestCsvProfile && GEngine != nullptr && GetWorld() != nullptr)
    {
        GEngine->Exec(GetWorld(), TEXT("csvprofile stop"));
    }
    WriteArtifacts();
    UE_LOG(LogTemp, Display, TEXT("PORCE_SPPA_PACKAGED_BENCHMARK_OK out=%s"), *OutDir);
    FGenericPlatformMisc::RequestExit(false);
}

void APorceSppaPackagedBenchmarkRunner::WriteArtifacts()
{
    IFileManager::Get().MakeDirectory(*OutDir, true);
    FFileHelper::SaveStringToFile(FrameRows, *FPaths::Combine(OutDir, TEXT("packaged_frame_stats.csv")));
    FFileHelper::SaveStringToFile(ActionRows, *FPaths::Combine(OutDir, TEXT("packaged_action_rows.csv")));
    FFileHelper::SaveStringToFile(FailureRows, *FPaths::Combine(OutDir, TEXT("packaged_failures.csv")));

    TSharedPtr<FJsonObject> Manifest = MakeShared<FJsonObject>();
    Manifest->SetStringField(TEXT("mode"), TEXT("packaged_internal_replay_render_stats"));
    Manifest->SetStringField(TEXT("claim_scope"), TEXT("Packaged executable internal obstacle replay with rendered frames; not live HTTP/network telemetry and estimated draw/triangle counts unless CSV profiler is parsed separately."));
    Manifest->SetStringField(TEXT("created_utc"), FDateTime::UtcNow().ToString(TEXT("%Y%m%dT%H%M%SZ")));
    Manifest->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
    Manifest->SetStringField(TEXT("command_line"), FCommandLine::Get());
    Manifest->SetStringField(TEXT("out_dir"), OutDir);
    Manifest->SetNumberField(TEXT("repetitions"), Repetitions);
    Manifest->SetNumberField(TEXT("warmup_frames"), WarmupFrames);
    Manifest->SetNumberField(TEXT("measure_frames"), MeasureFrames);
    Manifest->SetNumberField(TEXT("update_every_frames"), UpdateEveryFrames);
    Manifest->SetNumberField(TEXT("seed"), Seed);
    Manifest->SetBoolField(TEXT("csv_profile_requested"), bRequestCsvProfile);
    TArray<TSharedPtr<FJsonValue>> CountValues;
    for (int32 Count : Counts)
    {
        CountValues.Add(MakeShared<FJsonValueNumber>(Count));
    }
    Manifest->SetArrayField(TEXT("counts"), CountValues);
    TArray<TSharedPtr<FJsonValue>> BackendValues;
    for (const FString& Backend : Backends)
    {
        BackendValues.Add(MakeShared<FJsonValueString>(Backend));
    }
    Manifest->SetArrayField(TEXT("backends"), BackendValues);
    Manifest->SetArrayField(TEXT("artifacts"), {
        MakeShared<FJsonValueString>(TEXT("packaged_frame_stats.csv")),
        MakeShared<FJsonValueString>(TEXT("packaged_action_rows.csv")),
        MakeShared<FJsonValueString>(TEXT("packaged_failures.csv")),
        MakeShared<FJsonValueString>(TEXT("run_manifest.json"))
    });
    FFileHelper::SaveStringToFile(JsonToString(Manifest), *FPaths::Combine(OutDir, TEXT("run_manifest.json")));
}

void APorceSppaPackagedBenchmarkRunner::AppendFailure(const FString& Message)
{
    FailureRows += CsvEscape(Message) + TEXT("\n");
    UE_LOG(LogTemp, Warning, TEXT("PORCE_SPPA_PACKAGED_BENCHMARK_FAILURE %s"), *Message);
}
