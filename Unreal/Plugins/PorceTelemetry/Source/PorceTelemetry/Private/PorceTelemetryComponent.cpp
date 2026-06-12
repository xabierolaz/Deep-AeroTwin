#include "PorceTelemetryComponent.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformMisc.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UObjectGlobals.h"
#include "CesiumGlobeAnchorComponent.h"

#ifdef GetEnvironmentVariable
#undef GetEnvironmentVariable
#endif

DEFINE_LOG_CATEGORY_STATIC(LogPorceTelemetry, Log, All);

namespace
{
bool ParseEnvBool(const TCHAR* Key)
{
    const FString RawValue = FPlatformMisc::GetEnvironmentVariable(Key).TrimStartAndEnd();
    if (RawValue.IsEmpty())
    {
        return false;
    }
    const FString Normalized = RawValue.ToLower();
    return (
        Normalized == TEXT("1")
        || Normalized == TEXT("true")
        || Normalized == TEXT("yes")
        || Normalized == TEXT("on")
    );
}

float Clamp01(float Value)
{
    return FMath::Max(0.0f, FMath::Min(1.0f, Value));
}

UCesiumGlobeAnchorComponent* FindOrCreateGlobeAnchor(AActor* Actor)
{
    if (!IsValid(Actor))
    {
        return nullptr;
    }

    if (UCesiumGlobeAnchorComponent* Existing = Actor->FindComponentByClass<UCesiumGlobeAnchorComponent>())
    {
        return Existing;
    }

    const FName ComponentName = MakeUniqueObjectName(
        Actor,
        UCesiumGlobeAnchorComponent::StaticClass(),
        TEXT("PORCE_TwinAnchor")
    );

    UCesiumGlobeAnchorComponent* Created = NewObject<UCesiumGlobeAnchorComponent>(
        Actor,
        UCesiumGlobeAnchorComponent::StaticClass(),
        ComponentName
    );
    if (!IsValid(Created))
    {
        return nullptr;
    }

    Actor->AddInstanceComponent(Created);
    Created->RegisterComponent();
    Created->SetTeleportWhenUpdatingTransform(true);
    return Created;
}
}

UPorceTelemetryComponent::UPorceTelemetryComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = true;
}

void UPorceTelemetryComponent::BeginPlay()
{
    Super::BeginPlay();
    LastPollTs = FPlatformTime::Seconds();

    if (bEnabled && !IsTwinConsumerEnabled())
    {
        UE_LOG(
            LogPorceTelemetry,
            Warning,
            TEXT("PORCE Twin V2 consumer disabled (set PORCE_UNREAL_TWIN_ENABLE=1 to enable).")
        );
    }

    if (EndpointUrl.TrimStartAndEnd().IsEmpty())
    {
        EndpointUrl = FPlatformMisc::GetEnvironmentVariable(TEXT("PORCE_UNREAL_TWIN_URL"));
        if (EndpointUrl.TrimStartAndEnd().IsEmpty())
        {
            EndpointUrl = FPlatformMisc::GetEnvironmentVariable(TEXT("PORCE_UNREAL_TELEMETRY_URL"));
        }
    }

    const FString EndpointNormalized = EndpointUrl.TrimStartAndEnd().ToLower();
    if (EndpointNormalized.Contains(TEXT("/api/unreal/telemetry")))
    {
        EndpointUrl = TEXT("http://127.0.0.1:8080/api/ui/data");
        UE_LOG(
            LogPorceTelemetry,
            Warning,
            TEXT("PORCE Twin V2 migrated legacy endpoint to %s"),
            *EndpointUrl
        );
    }

    if (PollRateHz <= 0.0f)
    {
        PollRateHz = 5.0f;
    }

    auto EnsureClassLoaded = [this](TSubclassOf<AActor>& Slot, const TCHAR* ClassPath, const TCHAR* Label) -> void
    {
        if (Slot != nullptr)
        {
            return;
        }
        UClass* LoadedClass = StaticLoadClass(AActor::StaticClass(), nullptr, ClassPath);
        if (LoadedClass != nullptr)
        {
            Slot = LoadedClass;
            UE_LOG(LogPorceTelemetry, Log, TEXT("PORCE Twin V2 default class loaded: %s -> %s"), Label, ClassPath);
        }
        else
        {
            UE_LOG(LogPorceTelemetry, Verbose, TEXT("PORCE Twin V2 default class not found: %s (%s)"), Label, ClassPath);
        }
    };

    EnsureClassLoaded(TowerActorClass, TEXT("/Game/BP_Tower.BP_Tower_C"), TEXT("tower"));
    EnsureClassLoaded(CowActorClass, TEXT("/Game/BP_Cow.BP_Cow_C"), TEXT("cow"));
    EnsureClassLoaded(BikerActorClass, TEXT("/Game/BP_Biker.BP_Biker_C"), TEXT("biker"));
    EnsureClassLoaded(TowerActorClass, TEXT("/Game/bp_tower.bp_tower_C"), TEXT("tower"));
    EnsureClassLoaded(CowActorClass, TEXT("/Game/bp_cow.bp_cow_C"), TEXT("cow"));
    EnsureClassLoaded(BikerActorClass, TEXT("/Game/bp_biker.bp_biker_C"), TEXT("biker"));
}

void UPorceTelemetryComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    DestroyAllSpawnedActors();
    EntityStates.Empty();
    bRequestInFlight = false;
    Super::EndPlay(EndPlayReason);
}

void UPorceTelemetryComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (!bEnabled || !IsTwinConsumerEnabled())
    {
        return;
    }

    const double NowTs = FPlatformTime::Seconds();
    const double PollPeriodS = ResolvePollPeriodS();
    if (!bRequestInFlight && (PollPeriodS <= 0.0 || (NowTs - LastPollTs) >= PollPeriodS))
    {
        StartPollRequest(NowTs);
    }
    PruneStaleEntities(NowTs);
}

void UPorceTelemetryComponent::PollNow()
{
    if (!bEnabled || !IsTwinConsumerEnabled())
    {
        return;
    }

    StartPollRequest(FPlatformTime::Seconds());
}

void UPorceTelemetryComponent::SendNow()
{
    PollNow();
}

bool UPorceTelemetryComponent::IsTwinConsumerEnabled() const
{
    const FString TwinRaw = FPlatformMisc::GetEnvironmentVariable(TEXT("PORCE_UNREAL_TWIN_ENABLE")).TrimStartAndEnd();
    if (!TwinRaw.IsEmpty())
    {
        return ParseEnvBool(TEXT("PORCE_UNREAL_TWIN_ENABLE"));
    }

    const FString LegacyRaw = FPlatformMisc::GetEnvironmentVariable(TEXT("PORCE_UNREAL_TELEMETRY_ENABLE")).TrimStartAndEnd();
    if (!LegacyRaw.IsEmpty())
    {
        return ParseEnvBool(TEXT("PORCE_UNREAL_TELEMETRY_ENABLE"));
    }

    // Backward-compatible default: when no env flag is defined, honor component-level enable switch.
    return true;
}

double UPorceTelemetryComponent::ResolvePollPeriodS() const
{
    const double Hz = FMath::Max(0.0, static_cast<double>(PollRateHz));
    if (Hz <= KINDA_SMALL_NUMBER)
    {
        return 0.0;
    }
    return 1.0 / Hz;
}

FString UPorceTelemetryComponent::ResolveToken() const
{
    const FString LocalToken = AuthToken.TrimStartAndEnd();
    if (!LocalToken.IsEmpty())
    {
        return LocalToken;
    }

    FString Token = FPlatformMisc::GetEnvironmentVariable(TEXT("PORCE_UNREAL_TWIN_TOKEN")).TrimStartAndEnd();
    if (!Token.IsEmpty())
    {
        return Token;
    }
    Token = FPlatformMisc::GetEnvironmentVariable(TEXT("PORCE_UNREAL_TELEMETRY_TOKEN")).TrimStartAndEnd();
    if (!Token.IsEmpty())
    {
        return Token;
    }
    Token = FPlatformMisc::GetEnvironmentVariable(TEXT("PORCE_OBSTACLE_TOKEN")).TrimStartAndEnd();
    return Token;
}

bool UPorceTelemetryComponent::TryNEDToWorldCm(double NorthM, double EastM, double UpM, FVector& OutWorldCm) const
{
    const double A = static_cast<double>(EastFromLocalX);
    const double B = static_cast<double>(EastFromLocalY);
    const double C = static_cast<double>(NorthFromLocalX);
    const double D = static_cast<double>(NorthFromLocalY);
    const double Det = (A * D) - (B * C);

    double LocalXM = 0.0;
    double LocalYM = 0.0;
    if (FMath::Abs(Det) > 1e-6)
    {
        LocalXM = ((EastM * D) - (B * NorthM)) / Det;
        LocalYM = ((A * NorthM) - (EastM * C)) / Det;
    }
    else
    {
        LocalXM = NorthM;
        LocalYM = EastM;
    }

    const double ScaleMPerCm = FMath::Max(FMath::Abs(static_cast<double>(CmToMScale)), 1e-6);
    const FVector OriginCm = IsValid(OriginActor) ? OriginActor->GetActorLocation() : FVector::ZeroVector;

    OutWorldCm = OriginCm;
    OutWorldCm.X += static_cast<float>(LocalXM / ScaleMPerCm);
    OutWorldCm.Y += static_cast<float>(LocalYM / ScaleMPerCm);
    OutWorldCm.Z += static_cast<float>(ObstacleZOffsetCm);
    if (FMath::IsFinite(UpM))
    {
        OutWorldCm.Z += static_cast<float>(UpM / ScaleMPerCm);
    }
    return true;
}

bool UPorceTelemetryComponent::TryLatLonToWorldCm(double LatDeg, double LonDeg, FVector& OutWorldCm) const
{
    const double BaseLatDeg = static_cast<double>(HomeLatDeg);
    const double BaseLonDeg = static_cast<double>(HomeLonDeg);
    if (!FMath::IsFinite(BaseLatDeg) || !FMath::IsFinite(BaseLonDeg) || !FMath::IsFinite(LatDeg) || !FMath::IsFinite(LonDeg))
    {
        return false;
    }

    constexpr double EarthRadiusM = 6371000.0;
    const double BaseLatRad = FMath::DegreesToRadians(BaseLatDeg);
    const double DeltaLatRad = FMath::DegreesToRadians(LatDeg - BaseLatDeg);
    const double DeltaLonRad = FMath::DegreesToRadians(LonDeg - BaseLonDeg);
    const double CosLat = FMath::Max(FMath::Abs(FMath::Cos(BaseLatRad)), 1e-6);

    const double NorthM = DeltaLatRad * EarthRadiusM;
    const double EastM = DeltaLonRad * EarthRadiusM * CosLat;
    return TryNEDToWorldCm(NorthM, EastM, 0.0, OutWorldCm);
}

TSubclassOf<AActor> UPorceTelemetryComponent::ResolveActorClassForType(const FString& RawType) const
{
    const FString TypeKey = RawType.TrimStartAndEnd().ToLower();
    if (TypeKey == TEXT("tower"))
    {
        return TowerActorClass ? TowerActorClass : DefaultObstacleActorClass;
    }
    if (TypeKey == TEXT("cow"))
    {
        return CowActorClass ? CowActorClass : DefaultObstacleActorClass;
    }
    if (TypeKey == TEXT("bike") || TypeKey == TEXT("biker") || TypeKey == TEXT("person") || TypeKey == TEXT("bicycle"))
    {
        return BikerActorClass ? BikerActorClass : DefaultObstacleActorClass;
    }
    return DefaultObstacleActorClass;
}

void UPorceTelemetryComponent::StartPollRequest(double NowTs)
{
    if (bRequestInFlight)
    {
        return;
    }
    const FString Url = EndpointUrl.TrimStartAndEnd();
    if (Url.IsEmpty())
    {
        return;
    }

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(Url);
    Request->SetVerb(TEXT("GET"));
    Request->SetHeader(TEXT("Accept"), TEXT("application/json"));
    if (RequestTimeoutS > 0.01f)
    {
        Request->SetTimeout(static_cast<float>(RequestTimeoutS));
    }
    const FString Token = ResolveToken();
    if (!Token.IsEmpty())
    {
        Request->SetHeader(TEXT("X-PORCE-Token"), Token);
    }

    LastPollTs = NowTs;
    bRequestInFlight = true;
    Request->OnProcessRequestComplete().BindUObject(this, &UPorceTelemetryComponent::OnPollResponse);
    Request->ProcessRequest();
}

void UPorceTelemetryComponent::OnPollResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
    bRequestInFlight = false;
    if (!bConnectedSuccessfully || !Response.IsValid())
    {
        UE_LOG(LogPorceTelemetry, Verbose, TEXT("PORCE Twin V2 poll failed (connection)."));
        return;
    }

    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        UE_LOG(LogPorceTelemetry, Verbose, TEXT("PORCE Twin V2 poll invalid JSON response."));
        return;
    }

    const int32 StatusCode = Response->GetResponseCode();
    if (StatusCode < 200 || StatusCode >= 300)
    {
        UE_LOG(
            LogPorceTelemetry,
            Warning,
            TEXT("PORCE Twin V2 poll status=%d url=%s body=%s"),
            StatusCode,
            Request.IsValid() ? *Request->GetURL() : TEXT(""),
            *Response->GetContentAsString()
        );
        return;
    }

    const TArray<TSharedPtr<FJsonValue>>* Obstacles = nullptr;
    if (!Root->TryGetArrayField(TEXT("obstacles"), Obstacles) || Obstacles == nullptr)
    {
        UE_LOG(LogPorceTelemetry, Verbose, TEXT("PORCE Twin V2 poll response has no obstacles array."));
        return;
    }

    ApplyObstacleBatch(*Obstacles, FPlatformTime::Seconds());
}

void UPorceTelemetryComponent::ApplyObstacleBatch(const TArray<TSharedPtr<FJsonValue>>& Obstacles, double NowTs)
{
    for (const TSharedPtr<FJsonValue>& Value : Obstacles)
    {
        if (!Value.IsValid() || Value->Type != EJson::Object)
        {
            continue;
        }
        const TSharedPtr<FJsonObject> Obj = Value->AsObject();
        if (!Obj.IsValid())
        {
            continue;
        }

        FString EntityId;
        if (!Obj->TryGetStringField(TEXT("entity_id"), EntityId))
        {
            Obj->TryGetStringField(TEXT("object_id"), EntityId);
        }
        EntityId = EntityId.TrimStartAndEnd();
        if (EntityId.IsEmpty())
        {
            double FallbackId = -1.0;
            if (Obj->TryGetNumberField(TEXT("id"), FallbackId) && FallbackId >= 0.0)
            {
                EntityId = FString::Printf(TEXT("brain:%d"), static_cast<int32>(FallbackId));
            }
        }
        if (EntityId.IsEmpty())
        {
            continue;
        }

        FString ClassName = TEXT("unknown");
        if (!Obj->TryGetStringField(TEXT("object_type"), ClassName))
        {
            Obj->TryGetStringField(TEXT("type"), ClassName);
        }

        if (ClassName.TrimStartAndEnd().IsEmpty())
        {
            ClassName = TEXT("unknown");
        }

        double LatDeg = 0.0;
        double LonDeg = 0.0;
        const bool bHasLatLon = (
            Obj->TryGetNumberField(TEXT("lat"), LatDeg)
            && Obj->TryGetNumberField(TEXT("lon"), LonDeg)
            && FMath::IsFinite(LatDeg)
            && FMath::IsFinite(LonDeg)
        );

        double WorldNorthM = 0.0;
        double WorldEastM = 0.0;
        double WorldUpM = 0.0;
        bool bHasWorldNed = false;
        const TSharedPtr<FJsonObject>* WorldObj = nullptr;
        if (Obj->TryGetObjectField(TEXT("world_m"), WorldObj) && WorldObj != nullptr && WorldObj->IsValid())
        {
            const bool bHasNorth = (*WorldObj)->TryGetNumberField(TEXT("north"), WorldNorthM);
            const bool bHasEast = (*WorldObj)->TryGetNumberField(TEXT("east"), WorldEastM);
            double UpCandidate = 0.0;
            const bool bHasUp = (
                (*WorldObj)->TryGetNumberField(TEXT("up"), UpCandidate)
                || (*WorldObj)->TryGetNumberField(TEXT("z"), UpCandidate)
            );
            if (bHasNorth && bHasEast && FMath::IsFinite(WorldNorthM) && FMath::IsFinite(WorldEastM))
            {
                bHasWorldNed = true;
                if (bHasUp && FMath::IsFinite(UpCandidate))
                {
                    WorldUpM = UpCandidate;
                }
            }
        }

        if (!bHasWorldNed)
        {
            double NorthCandidate = 0.0;
            double EastCandidate = 0.0;
            const bool bHasNorthCandidate = Obj->TryGetNumberField(TEXT("world_north_m"), NorthCandidate);
            const bool bHasEastCandidate = Obj->TryGetNumberField(TEXT("world_east_m"), EastCandidate);
            if (bHasNorthCandidate && bHasEastCandidate && FMath::IsFinite(NorthCandidate) && FMath::IsFinite(EastCandidate))
            {
                bHasWorldNed = true;
                WorldNorthM = NorthCandidate;
                WorldEastM = EastCandidate;
                double UpCandidate = 0.0;
                if (Obj->TryGetNumberField(TEXT("world_up_m"), UpCandidate) && FMath::IsFinite(UpCandidate))
                {
                    WorldUpM = UpCandidate;
                }
            }
        }

        if (!bHasLatLon && !bHasWorldNed)
        {
            continue;
        }

        double ConfidenceD = 0.0;
        Obj->TryGetNumberField(TEXT("confidence"), ConfidenceD);
        const float Confidence = Clamp01(static_cast<float>(ConfidenceD));

        UpsertObstacle(
            EntityId,
            ClassName,
            bHasLatLon,
            LatDeg,
            LonDeg,
            bHasWorldNed,
            WorldNorthM,
            WorldEastM,
            WorldUpM,
            Confidence,
            NowTs
        );
    }

    PruneStaleEntities(NowTs);
}

void UPorceTelemetryComponent::UpsertObstacle(
    const FString& EntityId,
    const FString& ClassName,
    bool bHasLatLon,
    double LatDeg,
    double LonDeg,
    bool bHasWorldNed,
    double WorldNorthM,
    double WorldEastM,
    double WorldUpM,
    float Confidence,
    double NowTs
)
{
    const bool bCanUseLatLonForAnchor =
        bHasLatLon && FMath::IsFinite(LatDeg) && FMath::IsFinite(LonDeg);
    const double UpForAnchorM =
        (bHasWorldNed && FMath::IsFinite(WorldUpM)) ? WorldUpM : 0.0;

    FVector MeasuredWorldCm = FVector::ZeroVector;
    bool bHasWorld = false;
    if (bHasWorldNed)
    {
        bHasWorld = TryNEDToWorldCm(WorldNorthM, WorldEastM, WorldUpM, MeasuredWorldCm);
    }
    if (!bHasWorld && bHasLatLon)
    {
        bHasWorld = TryLatLonToWorldCm(LatDeg, LonDeg, MeasuredWorldCm);
    }
    if (!bHasWorld)
    {
        return;
    }

    FPorceTwinEntityState* Existing = EntityStates.Find(EntityId);
    if (Existing == nullptr)
    {
        FPorceTwinEntityState NewState;
        NewState.EntityId = EntityId;
        NewState.ClassName = ClassName;
        NewState.LastConfidence = Confidence;
        NewState.bConfirmed = Confidence >= ConfirmedConfidenceThreshold;
        NewState.LastSeenTs = NowTs;
        NewState.SmoothedWorldLocation = MeasuredWorldCm;
        EntityStates.Add(EntityId, NewState);
        Existing = EntityStates.Find(EntityId);
    }
    if (Existing == nullptr)
    {
        return;
    }

    Existing->ClassName = ClassName;
    Existing->LastConfidence = Confidence;
    Existing->bConfirmed = Existing->bConfirmed || (Confidence >= ConfirmedConfidenceThreshold);
    Existing->LastSeenTs = NowTs;

    const float Alpha = Existing->bConfirmed
        ? Clamp01(ConfirmedSmoothingAlpha)
        : Clamp01(TentativeSmoothingAlpha);
    Existing->SmoothedWorldLocation = FMath::Lerp(Existing->SmoothedWorldLocation, MeasuredWorldCm, Alpha);

    if (!Existing->SpawnedActor.IsValid())
    {
        UWorld* World = GetWorld();
        TSubclassOf<AActor> ActorClass = ResolveActorClassForType(ClassName);
        if (World != nullptr && ActorClass != nullptr)
        {
            FActorSpawnParameters SpawnParams;
            SpawnParams.Owner = GetOwner();
            SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            AActor* Spawned = World->SpawnActor<AActor>(
                ActorClass,
                Existing->SmoothedWorldLocation,
                FRotator::ZeroRotator,
                SpawnParams
            );
            if (IsValid(Spawned))
            {
                Existing->SpawnedActor = Spawned;
                UE_LOG(
                    LogPorceTelemetry,
                    Log,
                    TEXT(
                        "PORCE Twin V2 SPAWN entity=%s type=%s conf=%.3f world_cm=(%.1f, %.1f, %.1f) "
                        "src_ned_m=(%s, %s, %s) src_latlon=(%s, %s) mode=%s"
                    ),
                    *EntityId,
                    *ClassName,
                    static_cast<double>(Confidence),
                    static_cast<double>(Existing->SmoothedWorldLocation.X),
                    static_cast<double>(Existing->SmoothedWorldLocation.Y),
                    static_cast<double>(Existing->SmoothedWorldLocation.Z),
                    bHasWorldNed ? *FString::SanitizeFloat(WorldNorthM) : TEXT("-"),
                    bHasWorldNed ? *FString::SanitizeFloat(WorldEastM) : TEXT("-"),
                    bHasWorldNed ? *FString::SanitizeFloat(WorldUpM) : TEXT("-"),
                    bHasLatLon ? *FString::SanitizeFloat(LatDeg) : TEXT("-"),
                    bHasLatLon ? *FString::SanitizeFloat(LonDeg) : TEXT("-"),
                    bCanUseLatLonForAnchor ? TEXT("cesium") : TEXT("local")
                );
            }
        }
    }

    if (Existing->SpawnedActor.IsValid())
    {
        bool bMovedByCesium = false;
        if (bCanUseLatLonForAnchor)
        {
            if (UCesiumGlobeAnchorComponent* GlobeAnchor = FindOrCreateGlobeAnchor(Existing->SpawnedActor.Get()))
            {
                if (!Existing->bCesiumBaseHeightInitialized)
                {
                    const FVector CurrentLLH = GlobeAnchor->GetLongitudeLatitudeHeight();
                    Existing->CesiumBaseHeightM = FMath::IsFinite(CurrentLLH.Z) ? static_cast<double>(CurrentLLH.Z) : 0.0;
                    Existing->bCesiumBaseHeightInitialized = true;
                }

                const double TargetHeightM = Existing->CesiumBaseHeightM + UpForAnchorM;
                const FVector TargetLLH(
                    static_cast<float>(LonDeg),
                    static_cast<float>(LatDeg),
                    static_cast<float>(TargetHeightM)
                );
                GlobeAnchor->MoveToLongitudeLatitudeHeight(TargetLLH);
                bMovedByCesium = true;
                Existing->SmoothedWorldLocation = Existing->SpawnedActor->GetActorLocation();
            }
        }

        if (!bMovedByCesium)
        {
            Existing->SpawnedActor->SetActorLocation(Existing->SmoothedWorldLocation, false, nullptr, ETeleportType::TeleportPhysics);
        }
        Existing->SpawnedActor->SetActorHiddenInGame(bHideUnconfirmedActors && !Existing->bConfirmed);
        Existing->SpawnedActor->SetActorEnableCollision(Existing->bConfirmed);
    }
}

void UPorceTelemetryComponent::PruneStaleEntities(double NowTs)
{
    const double KeepS = FMath::Max(0.05, static_cast<double>(DespawnAfterS));
    TArray<FString> ToRemove;
    ToRemove.Reserve(EntityStates.Num());
    for (const TPair<FString, FPorceTwinEntityState>& Pair : EntityStates)
    {
        const FPorceTwinEntityState& State = Pair.Value;
        if ((NowTs - State.LastSeenTs) <= KeepS)
        {
            continue;
        }
        if (State.SpawnedActor.IsValid())
        {
            State.SpawnedActor->Destroy();
        }
        ToRemove.Add(Pair.Key);
    }
    for (const FString& Key : ToRemove)
    {
        EntityStates.Remove(Key);
    }
}

void UPorceTelemetryComponent::DestroyAllSpawnedActors()
{
    for (TPair<FString, FPorceTwinEntityState>& Pair : EntityStates)
    {
        if (Pair.Value.SpawnedActor.IsValid())
        {
            Pair.Value.SpawnedActor->Destroy();
        }
    }
}
