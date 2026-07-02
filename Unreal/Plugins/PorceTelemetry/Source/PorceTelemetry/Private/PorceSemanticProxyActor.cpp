#include "PorceSemanticProxyActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
float Clamp01Local(float Value)
{
    return FMath::Max(0.0f, FMath::Min(1.0f, Value));
}

FString SanitizeTagValue(const FString& RawValue)
{
    FString Value = RawValue.TrimStartAndEnd();
    if (Value.IsEmpty())
    {
        return TEXT("unknown");
    }
    Value.ReplaceInline(TEXT(" "), TEXT("_"));
    Value.ReplaceInline(TEXT("/"), TEXT("_"));
    Value.ReplaceInline(TEXT("\\"), TEXT("_"));
    Value.ReplaceInline(TEXT(":"), TEXT("_"));
    return Value;
}

FString NormalizeResolverMatchType(const FString& RawValue)
{
    const FString Value = RawValue.TrimStartAndEnd();
    if (Value == TEXT("exact_class"))
    {
        return TEXT("exact");
    }
    if (Value == TEXT("keyword_archetype"))
    {
        return TEXT("keyword");
    }
    if (Value.StartsWith(TEXT("fallback")))
    {
        return TEXT("fallback_unknown");
    }
    return Value;
}

void AddSanitizedTag(AActor* Actor, const FString& Prefix, const FString& Value)
{
    if (!IsValid(Actor))
    {
        return;
    }
    Actor->Tags.AddUnique(*FString::Printf(TEXT("%s%s"), *Prefix, *SanitizeTagValue(Value)));
}

FString GetJsonString(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, const FString& DefaultValue = FString())
{
    if (!Obj.IsValid())
    {
        return DefaultValue;
    }
    FString Value;
    return Obj->TryGetStringField(Field, Value) ? Value : DefaultValue;
}

bool GetJsonBool(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool DefaultValue = false)
{
    if (!Obj.IsValid())
    {
        return DefaultValue;
    }
    bool Value = DefaultValue;
    return Obj->TryGetBoolField(Field, Value) ? Value : DefaultValue;
}

double GetJsonNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, double DefaultValue = 0.0)
{
    if (!Obj.IsValid())
    {
        return DefaultValue;
    }
    double Value = DefaultValue;
    return Obj->TryGetNumberField(Field, Value) ? Value : DefaultValue;
}

TSharedPtr<FJsonObject> GetJsonObject(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field)
{
    if (!Obj.IsValid())
    {
        return nullptr;
    }
    const TSharedPtr<FJsonObject>* Child = nullptr;
    if (Obj->TryGetObjectField(Field, Child) && Child != nullptr && Child->IsValid())
    {
        return *Child;
    }
    return nullptr;
}

FString ResolveScaleSource(const TSharedPtr<FJsonObject>& Root)
{
    const TSharedPtr<FJsonObject> Scale = GetJsonObject(Root, TEXT("scale"));
    const FString ScaleSource = GetJsonString(Scale, TEXT("scale_source"));
    if (!ScaleSource.IsEmpty())
    {
        return ScaleSource;
    }
    const TSharedPtr<FJsonObject> Uncertainty = GetJsonObject(Root, TEXT("uncertainty"));
    if (GetJsonBool(Uncertainty, TEXT("scale_from_dims"), false))
    {
        return TEXT("metric_dims_input");
    }
    if (GetJsonBool(Uncertainty, TEXT("scale_from_mask"), false))
    {
        return TEXT("mask_footprint_px");
    }
    if (GetJsonBool(Uncertainty, TEXT("scale_from_bbox"), false))
    {
        return TEXT("bbox_px");
    }
    return TEXT("template_prior");
}

FString ResolveMaterialSource(const TSharedPtr<FJsonObject>& Root, bool bFallbackUnknown)
{
    const TSharedPtr<FJsonObject> Uncertainty = GetJsonObject(Root, TEXT("uncertainty"));
    const FString MaterialSource = GetJsonString(Uncertainty, TEXT("material_source"));
    if (!MaterialSource.IsEmpty())
    {
        return MaterialSource;
    }
    return bFallbackUnknown ? TEXT("fallback_unknown") : TEXT("semantic_prior");
}

bool TryReadNumberArray(const TArray<TSharedPtr<FJsonValue>>& Values, TArray<double>& OutValues)
{
    OutValues.Reset();
    OutValues.Reserve(Values.Num());
    for (const TSharedPtr<FJsonValue>& Value : Values)
    {
        if (!Value.IsValid())
        {
            return false;
        }
        double Number = 0.0;
        if (!Value->TryGetNumber(Number) || !FMath::IsFinite(Number))
        {
            return false;
        }
        OutValues.Add(Number);
    }
    return true;
}

bool TryReadNumberArrayField(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, TArray<double>& OutValues)
{
    if (!Obj.IsValid())
    {
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Obj->TryGetArrayField(Field, Values) || Values == nullptr)
    {
        return false;
    }
    return TryReadNumberArray(*Values, OutValues);
}

bool IsValidDescriptorPart(const TSharedPtr<FJsonObject>& PartObj)
{
    if (!PartObj.IsValid())
    {
        return false;
    }
    const TSharedPtr<FJsonObject> PoseObj = GetJsonObject(PartObj, TEXT("local_pose"));
    TArray<double> Center;
    TArray<double> Scale;
    return (
        PoseObj.IsValid()
        && TryReadNumberArrayField(PoseObj, TEXT("center"), Center)
        && Center.Num() >= 3
        && TryReadNumberArrayField(PartObj, TEXT("scale"), Scale)
        && Scale.Num() >= 3
    );
}

FRotator RotationForDescriptorAxis(const FString& Axis)
{
    const FString Normalized = Axis.TrimStartAndEnd().ToLower();
    if (Normalized == TEXT("x"))
    {
        return FRotator(90.0f, 0.0f, 0.0f);
    }
    if (Normalized == TEXT("y"))
    {
        return FRotator(0.0f, 0.0f, 90.0f);
    }
    return FRotator::ZeroRotator;
}

FVector ScaleForDescriptorPrimitive(const FString& Primitive, const TArray<double>& RawScale)
{
    const FString Normalized = Primitive.TrimStartAndEnd().ToLower();
    const double A = RawScale.Num() > 0 ? RawScale[0] : 1.0;
    const double B = RawScale.Num() > 1 ? RawScale[1] : A;
    const double C = RawScale.Num() > 2 ? RawScale[2] : A;

    if (Normalized == TEXT("sphere"))
    {
        return FVector(static_cast<float>(A * 2.0), static_cast<float>(B * 2.0), static_cast<float>(C * 2.0));
    }
    if (Normalized == TEXT("cylinder") || Normalized == TEXT("cone"))
    {
        return FVector(static_cast<float>(A * 2.0), static_cast<float>(B * 2.0), static_cast<float>(C));
    }
    if (Normalized == TEXT("torus"))
    {
        const double Major = FMath::Max(0.0, A);
        const double Minor = FMath::Max(0.0, B);
        const double OuterDiameter = FMath::Max(0.01, (Major + Minor) * 2.0);
        const double Depth = FMath::Max(0.01, Minor * 2.0);
        return FVector(static_cast<float>(OuterDiameter), static_cast<float>(OuterDiameter), static_cast<float>(Depth));
    }
    return FVector(static_cast<float>(A), static_cast<float>(B), static_cast<float>(C));
}

FName ShapeForDescriptorPrimitive(const FString& Primitive)
{
    const FString Normalized = Primitive.TrimStartAndEnd().ToLower();
    if (Normalized == TEXT("sphere"))
    {
        return TEXT("sphere");
    }
    if (Normalized == TEXT("cylinder") || Normalized == TEXT("torus"))
    {
        return TEXT("cylinder");
    }
    if (Normalized == TEXT("cone"))
    {
        return TEXT("cone");
    }
    return TEXT("cube");
}

bool TryReadDimsM(const TSharedPtr<FJsonObject>& Obj, FVector& OutDimsM)
{
    const TSharedPtr<FJsonObject> ScaleObj = GetJsonObject(Obj, TEXT("scale"));
    const TSharedPtr<FJsonObject> DimsObj = GetJsonObject(ScaleObj, TEXT("dims_m"));
    if (!DimsObj.IsValid())
    {
        return false;
    }

    const double Length = GetJsonNumber(DimsObj, TEXT("length"), 0.0);
    const double Width = GetJsonNumber(DimsObj, TEXT("width"), 0.0);
    const double Height = GetJsonNumber(DimsObj, TEXT("height"), 0.0);
    if (Length <= 0.0 || Width <= 0.0 || Height <= 0.0)
    {
        return false;
    }
    if (!FMath::IsFinite(Length) || !FMath::IsFinite(Width) || !FMath::IsFinite(Height))
    {
        return false;
    }

    OutDimsM = FVector(static_cast<float>(Length), static_cast<float>(Width), static_cast<float>(Height));
    return true;
}
}

APorceSemanticProxyActor::APorceSemanticProxyActor()
{
    PrimaryActorTick.bCanEverTick = false;

    ProxyRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SPPAProxyRoot"));
    RootComponent = ProxyRoot;

    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereFinder(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderFinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeFinder(TEXT("/Engine/BasicShapes/Cone.Cone"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));

    CubeMesh = CubeFinder.Object;
    SphereMesh = SphereFinder.Object;
    CylinderMesh = CylinderFinder.Object;
    ConeMesh = ConeFinder.Object;
    BasicShapeMaterial = MaterialFinder.Object;
}

void APorceSemanticProxyActor::ConfigureProxy(const FString& ClassName, float Confidence, bool bConfirmed)
{
    FString TypeKey = ClassName.TrimStartAndEnd().ToLower();
    if (TypeKey.IsEmpty())
    {
        TypeKey = TEXT("unknown");
    }
    const float ConfidenceAlpha = FMath::Clamp(Confidence, 0.0f, 1.0f);
    const int32 ConfidenceBucket = FMath::RoundToInt(ConfidenceAlpha * 20.0f);
    if (
        GeneratedComponents.Num() > 0
        && LastConfiguredClassKey == TypeKey
        && LastConfiguredConfidenceBucket == ConfidenceBucket
        && bLastConfiguredConfirmed == bConfirmed
        && bLastConfiguredUseEvidenceMaterials == bUseEvidenceCalibratedMaterials
    )
    {
        return;
    }

    ClearProxy();
    ClearClassTags();
    LastConfiguredClassKey = TypeKey;
    LastConfiguredConfidenceBucket = ConfidenceBucket;
    bLastConfiguredConfirmed = bConfirmed;
    bLastConfiguredUseEvidenceMaterials = bUseEvidenceCalibratedMaterials;
    LastConfiguredDescriptorId.Reset();
    LastConfiguredDescriptorAction.Reset();
    bHasDescriptorReferenceDimsM = false;
    DescriptorReferenceDimsM = FVector::OneVector;
    LastAppliedDescriptorScale = FVector::OneVector;
    ProxyRoot->SetRelativeScale3D(FVector::OneVector);
    CurrentConfidenceAlpha = ConfidenceAlpha;
    bCurrentProxyUsesFallback = false;

    FLinearColor Color = bConfirmed ? ConfirmedColor : TentativeColor;
    Color.A = FMath::Lerp(0.45f, 1.0f, ConfidenceAlpha);

    const bool bBikerLike =
        TypeKey.Contains(TEXT("bike"))
        || TypeKey.Contains(TEXT("bicycle"))
        || TypeKey.Contains(TEXT("cyclist"))
        || TypeKey.Contains(TEXT("rider"))
        || TypeKey.Contains(TEXT("person"))
        || TypeKey.Contains(TEXT("pedestrian"));

    const bool bVehicleLike =
        TypeKey.Contains(TEXT("car"))
        || TypeKey.Contains(TEXT("vehicle"))
        || TypeKey.Contains(TEXT("van"))
        || TypeKey.Contains(TEXT("truck"))
        || TypeKey.Contains(TEXT("tractor"))
        || TypeKey.Contains(TEXT("bus"))
        || TypeKey.Contains(TEXT("ambulance"))
        || TypeKey.Contains(TEXT("pickup"));

    const bool bVegetationLike =
        TypeKey.Contains(TEXT("tree"))
        || TypeKey.Contains(TEXT("bush"))
        || TypeKey.Contains(TEXT("plant"))
        || TypeKey.Contains(TEXT("vegetation"))
        || TypeKey.Contains(TEXT("shrub"));

    const bool bTowerLike =
        TypeKey.Contains(TEXT("tower"))
        || TypeKey.Contains(TEXT("pole"))
        || TypeKey.Contains(TEXT("mast"))
        || TypeKey.Contains(TEXT("pylon"))
        || TypeKey.Contains(TEXT("antenna"))
        || TypeKey.Contains(TEXT("post"));

    const bool bAnimalLike =
        TypeKey.Contains(TEXT("cow"))
        || TypeKey.Contains(TEXT("animal"))
        || TypeKey.Contains(TEXT("horse"))
        || TypeKey.Contains(TEXT("sheep"))
        || TypeKey.Contains(TEXT("goat"))
        || TypeKey.Contains(TEXT("dog"))
        || TypeKey.Contains(TEXT("deer"));

    if (bTowerLike)
    {
        BuildTowerProxy(Color, bConfirmed);
    }
    else if (bAnimalLike)
    {
        BuildCowProxy(Color, bConfirmed);
    }
    else if (bVehicleLike)
    {
        BuildVehicleProxy(Color, bConfirmed);
    }
    else if (bVegetationLike)
    {
        BuildVegetationProxy(Color, bConfirmed);
    }
    else if (bBikerLike)
    {
        BuildBikerProxy(Color, bConfirmed);
    }
    else
    {
        bCurrentProxyUsesFallback = true;
        FLinearColor FallbackColor = UnknownColor;
        FallbackColor.A = Color.A;
        BuildUnknownProxy(FallbackColor, bConfirmed);
    }

    Tags.AddUnique(TEXT("PORCE_SPPA_PROXY"));
    Tags.AddUnique(*FString::Printf(TEXT("PORCE_CLASS_%s"), *TypeKey));
    Tags.AddUnique(bUseEvidenceCalibratedMaterials ? TEXT("PORCE_MATERIAL_POLICY_evidence_calibrated_procedural_roles") : TEXT("PORCE_MATERIAL_POLICY_flat_class_color"));
}

bool APorceSemanticProxyActor::ConfigureProxyFromDescriptorJson(const FString& DescriptorJson, bool bConfirmed)
{
    const FString TrimmedJson = DescriptorJson.TrimStartAndEnd();
    if (TrimmedJson.IsEmpty())
    {
        return false;
    }

    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(TrimmedJson);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        return false;
    }

    const FString DescriptorSchema = GetJsonString(Root, TEXT("descriptor_schema"));
    const FString PacketSchema = GetJsonString(Root, TEXT("packet_schema"));
    if (DescriptorSchema != TEXT("SPPA-DESC-0.2") && PacketSchema != TEXT("SPPA-UPD-0.2"))
    {
        return false;
    }

    const FString DescriptorId = SanitizeTagValue(GetJsonString(Root, TEXT("descriptor_id"), TEXT("unknown_descriptor")));
    FString Action = GetJsonString(Root, TEXT("action"));
    if (Action.IsEmpty())
    {
        const TSharedPtr<FJsonObject> RuntimePolicy = GetJsonObject(Root, TEXT("runtime_policy"));
        Action = GetJsonString(RuntimePolicy, TEXT("action"), TEXT("create"));
    }
    Action = SanitizeTagValue(Action);

    const TSharedPtr<FJsonObject> Resolver = GetJsonObject(Root, TEXT("resolver"));
    const TSharedPtr<FJsonObject> Semantic = GetJsonObject(Root, TEXT("semantic"));
    const TSharedPtr<FJsonObject> Uncertainty = GetJsonObject(Root, TEXT("uncertainty"));
    const TSharedPtr<FJsonObject> Input = GetJsonObject(Root, TEXT("input"));
    const FString ClassKey = SanitizeTagValue(GetJsonString(Semantic, TEXT("normalized_label"), GetJsonString(Input, TEXT("normalized_label"), TEXT("unknown"))));
    const FString ArchetypeId = SanitizeTagValue(GetJsonString(Resolver, TEXT("archetype_id"), GetJsonString(Semantic, TEXT("archetype"), TEXT("unknown"))));
    const FString MatchType = SanitizeTagValue(NormalizeResolverMatchType(GetJsonString(Resolver, TEXT("match_type"), GetJsonString(Semantic, TEXT("match_type"), GetJsonString(Semantic, TEXT("resolution_status"), TEXT("unknown"))))));
    const FString ResolverSource = SanitizeTagValue(GetJsonString(Resolver, TEXT("resolver_source"), TEXT("unspecified")));
    const bool bFallbackUnknown =
        GetJsonBool(Semantic, TEXT("unknown_label"), false)
        || GetJsonBool(Uncertainty, TEXT("fallback_unknown"), false)
        || MatchType == TEXT("fallback_unknown");
    const bool bYawAmbiguous =
        GetJsonBool(Uncertainty, TEXT("yaw_ambiguous"), false)
        || GetJsonBool(GetJsonObject(Root, TEXT("pose")), TEXT("yaw_ambiguous"), false);
    const bool bShapeLowConfidence = GetJsonBool(Uncertainty, TEXT("shape_low_confidence"), false);
    const FString ScaleSource = SanitizeTagValue(ResolveScaleSource(Root));
    const FString MaterialSource = SanitizeTagValue(ResolveMaterialSource(Root, bFallbackUnknown));

    if ((Action == TEXT("no_op") || Action == TEXT("pose_update")) && GeneratedComponents.Num() > 0)
    {
        if (
            !LastConfiguredDescriptorId.IsEmpty()
            && DescriptorId != TEXT("unknown_descriptor")
            && LastConfiguredDescriptorId != DescriptorId
        )
        {
            return false;
        }
        ClearClassTags();

        LastConfiguredDescriptorId = DescriptorId;
        LastConfiguredDescriptorAction = Action;
        Tags.AddUnique(TEXT("PORCE_SPPA_DESCRIPTOR"));
        Tags.AddUnique(*FString::Printf(TEXT("PORCE_DESCRIPTOR_%s"), *DescriptorId));
        Tags.AddUnique(*FString::Printf(TEXT("PORCE_DESCRIPTOR_ACTION_%s"), *Action));
        AddSanitizedTag(this, TEXT("PORCE_CLASS_"), ClassKey);
        AddSanitizedTag(this, TEXT("PORCE_ARCHETYPE_"), ArchetypeId);
        AddSanitizedTag(this, TEXT("PORCE_RESOLVER_MATCH_"), MatchType);
        AddSanitizedTag(this, TEXT("PORCE_RESOLVER_SOURCE_"), ResolverSource);
        AddSanitizedTag(this, TEXT("PORCE_SCALE_SOURCE_"), ScaleSource);
        AddSanitizedTag(this, TEXT("PORCE_MATERIAL_SOURCE_"), MaterialSource);
        if (bFallbackUnknown)
        {
            Tags.AddUnique(TEXT("PORCE_UNCERTAINTY_FALLBACK_UNKNOWN"));
        }
        if (bYawAmbiguous)
        {
            Tags.AddUnique(TEXT("PORCE_UNCERTAINTY_YAW_AMBIGUOUS"));
        }
        if (bShapeLowConfidence)
        {
            Tags.AddUnique(TEXT("PORCE_UNCERTAINTY_SHAPE_LOW_CONFIDENCE"));
        }
        return true;
    }

    const TArray<TSharedPtr<FJsonValue>>* Parts = nullptr;
    if (!Root->TryGetArrayField(TEXT("parts"), Parts) || Parts == nullptr || Parts->Num() <= 0)
    {
        return false;
    }

    int32 ValidPartCount = 0;
    for (const TSharedPtr<FJsonValue>& PartValue : *Parts)
    {
        if (PartValue.IsValid() && PartValue->Type == EJson::Object && IsValidDescriptorPart(PartValue->AsObject()))
        {
            ++ValidPartCount;
        }
    }
    if (ValidPartCount <= 0)
    {
        return false;
    }

    if (
        GeneratedComponents.Num() > 0
        && LastConfiguredDescriptorId == DescriptorId
        && LastConfiguredDescriptorAction == Action
        && bLastConfiguredConfirmed == bConfirmed
        && bLastConfiguredUseEvidenceMaterials == bUseEvidenceCalibratedMaterials
    )
    {
        return true;
    }

    const double RawConfidence = GetJsonNumber(
        Semantic,
        TEXT("class_confidence"),
        GetJsonNumber(Uncertainty, TEXT("confidence"), GetJsonNumber(Input, TEXT("confidence"), 1.0))
    );
    const float ConfidenceAlpha = Clamp01Local(static_cast<float>(RawConfidence));

    ClearProxy();
    ClearClassTags();
    LastConfiguredClassKey = ClassKey;
    LastConfiguredConfidenceBucket = FMath::RoundToInt(ConfidenceAlpha * 20.0f);
    bLastConfiguredConfirmed = bConfirmed;
    bLastConfiguredUseEvidenceMaterials = bUseEvidenceCalibratedMaterials;
    LastConfiguredDescriptorId = DescriptorId;
    LastConfiguredDescriptorAction = Action;
    CurrentConfidenceAlpha = ConfidenceAlpha;
    bCurrentProxyUsesFallback = bFallbackUnknown;
    ProxyRoot->SetRelativeScale3D(FVector::OneVector);
    LastAppliedDescriptorScale = FVector::OneVector;
    bHasDescriptorReferenceDimsM = TryReadDimsM(Root, DescriptorReferenceDimsM);

    FLinearColor BaseColor = bConfirmed ? ConfirmedColor : TentativeColor;
    if (bFallbackUnknown)
    {
        BaseColor = UnknownColor;
    }
    BaseColor.A = FMath::Lerp(0.45f, 1.0f, ConfidenceAlpha);

    int32 AddedPartCount = 0;
    const int32 Limit = FMath::Max(1, MaxDescriptorParts);
    for (const TSharedPtr<FJsonValue>& PartValue : *Parts)
    {
        if (AddedPartCount >= Limit)
        {
            break;
        }
        if (!PartValue.IsValid() || PartValue->Type != EJson::Object)
        {
            continue;
        }
        const TSharedPtr<FJsonObject> PartObj = PartValue->AsObject();
        if (!IsValidDescriptorPart(PartObj))
        {
            continue;
        }

        const FString Primitive = GetJsonString(PartObj, TEXT("primitive"), TEXT("box"));
        const FString PartRole = SanitizeTagValue(GetJsonString(PartObj, TEXT("role"), FString::Printf(TEXT("part_%d"), AddedPartCount)));
        const FString MaterialRole = SanitizeTagValue(GetJsonString(PartObj, TEXT("material_role"), PartRole));
        FString EvidenceSource = SanitizeTagValue(GetJsonString(PartObj, TEXT("evidence_source"), bFallbackUnknown ? TEXT("fallback_unknown") : TEXT("semantic_prior")));
        FString UncertaintyStyle = bFallbackUnknown ? TEXT("desaturated_unknown") : TEXT("none");
        if (ConfidenceAlpha < 0.50f && !bFallbackUnknown)
        {
            UncertaintyStyle = TEXT("low_confidence_desaturation");
        }
        if (MaterialRole == TEXT("uncertainty_marker"))
        {
            UncertaintyStyle = TEXT("warning_marker");
            EvidenceSource = TEXT("fallback_unknown");
        }

        const TSharedPtr<FJsonObject> PoseObj = GetJsonObject(PartObj, TEXT("local_pose"));
        TArray<double> Center;
        TArray<double> RawScale;
        TryReadNumberArrayField(PoseObj, TEXT("center"), Center);
        TryReadNumberArrayField(PartObj, TEXT("scale"), RawScale);

        const FString Axis = GetJsonString(PoseObj, TEXT("axis"), TEXT("z"));
        const FVector RelativeLocation(
            static_cast<float>(Center[0] * DescriptorMetersToCentimeters),
            static_cast<float>(Center[1] * DescriptorMetersToCentimeters),
            static_cast<float>(Center[2] * DescriptorMetersToCentimeters)
        );
        const FRotator RelativeRotation =
            (Primitive.ToLower() == TEXT("cylinder") || Primitive.ToLower() == TEXT("cone") || Primitive.ToLower() == TEXT("torus"))
                ? RotationForDescriptorAxis(Axis)
                : FRotator::ZeroRotator;
        const FVector RelativeScale = ScaleForDescriptorPrimitive(Primitive, RawScale);

        if (AddPart(
            ShapeForDescriptorPrimitive(Primitive),
            *PartRole,
            RelativeLocation,
            RelativeRotation,
            RelativeScale,
            BaseColor,
            bConfirmed,
            *MaterialRole,
            *EvidenceSource,
            *UncertaintyStyle
        ) != nullptr)
        {
            ++AddedPartCount;
        }
    }

    if (AddedPartCount <= 0)
    {
        ClearProxy();
        return false;
    }
    if (!bHasDescriptorReferenceDimsM)
    {
        bHasDescriptorReferenceDimsM = TryInferDescriptorReferenceDimsM(DescriptorReferenceDimsM);
    }

    Tags.AddUnique(TEXT("PORCE_SPPA_PROXY"));
    Tags.AddUnique(TEXT("PORCE_SPPA_DESCRIPTOR"));
    Tags.AddUnique(*FString::Printf(TEXT("PORCE_CLASS_%s"), *ClassKey));
    Tags.AddUnique(*FString::Printf(TEXT("PORCE_DESCRIPTOR_%s"), *DescriptorId));
    Tags.AddUnique(*FString::Printf(TEXT("PORCE_DESCRIPTOR_ACTION_%s"), *Action));
    AddSanitizedTag(this, TEXT("PORCE_ARCHETYPE_"), ArchetypeId);
    AddSanitizedTag(this, TEXT("PORCE_RESOLVER_MATCH_"), MatchType);
    AddSanitizedTag(this, TEXT("PORCE_RESOLVER_SOURCE_"), ResolverSource);
    AddSanitizedTag(this, TEXT("PORCE_SCALE_SOURCE_"), ScaleSource);
    AddSanitizedTag(this, TEXT("PORCE_MATERIAL_SOURCE_"), MaterialSource);
    if (bFallbackUnknown)
    {
        Tags.AddUnique(TEXT("PORCE_UNCERTAINTY_FALLBACK_UNKNOWN"));
    }
    if (bYawAmbiguous)
    {
        Tags.AddUnique(TEXT("PORCE_UNCERTAINTY_YAW_AMBIGUOUS"));
    }
    if (bShapeLowConfidence)
    {
        Tags.AddUnique(TEXT("PORCE_UNCERTAINTY_SHAPE_LOW_CONFIDENCE"));
    }
    Tags.AddUnique(bUseEvidenceCalibratedMaterials ? TEXT("PORCE_MATERIAL_POLICY_evidence_calibrated_procedural_roles") : TEXT("PORCE_MATERIAL_POLICY_flat_class_color"));
    return true;
}

bool APorceSemanticProxyActor::ApplyProxyUpdatePacketJson(const FString& UpdatePacketJson, bool bConfirmed)
{
    return ConfigureProxyFromDescriptorJson(UpdatePacketJson, bConfirmed);
}

void APorceSemanticProxyActor::ClearClassTags()
{
    Tags.RemoveAll([](const FName& Tag)
    {
        const FString Text = Tag.ToString();
        return (
            Text == TEXT("PORCE_SPPA_DESCRIPTOR")
            || Text.StartsWith(TEXT("PORCE_CLASS_"))
            || Text.StartsWith(TEXT("PORCE_ARCHETYPE_"))
            || Text.StartsWith(TEXT("PORCE_RESOLVER_MATCH_"))
            || Text.StartsWith(TEXT("PORCE_RESOLVER_SOURCE_"))
            || Text.StartsWith(TEXT("PORCE_SCALE_SOURCE_"))
            || Text.StartsWith(TEXT("PORCE_MATERIAL_SOURCE_"))
            || Text.StartsWith(TEXT("PORCE_UNCERTAINTY_"))
            || Text.StartsWith(TEXT("PORCE_MATERIAL_POLICY_"))
            || Text.StartsWith(TEXT("PORCE_DESCRIPTOR_"))
        );
    });
}

void APorceSemanticProxyActor::ClearProxy()
{
    for (UStaticMeshComponent* Component : GeneratedComponents)
    {
        if (IsValid(Component))
        {
            Component->DestroyComponent();
        }
    }
    GeneratedComponents.Empty();
}

UStaticMesh* APorceSemanticProxyActor::ResolveMesh(const FName& ShapeName) const
{
    if (ShapeName == TEXT("sphere"))
    {
        return SphereMesh;
    }
    if (ShapeName == TEXT("cylinder"))
    {
        return CylinderMesh;
    }
    if (ShapeName == TEXT("cone"))
    {
        return ConeMesh;
    }
    return CubeMesh;
}


FName APorceSemanticProxyActor::ResolveMaterialRole(const FName& PartName) const
{
    const FString Part = PartName.ToString().ToLower();
    if (Part.Contains(TEXT("unknownuncertainty")))
    {
        return TEXT("uncertainty_marker");
    }
    if (Part.Contains(TEXT("unknownfootprint")))
    {
        return TEXT("unknown_footprint");
    }
    if (Part.Contains(TEXT("unknown")))
    {
        return TEXT("unknown_conservative_volume");
    }
    if (Part.Contains(TEXT("wheel")))
    {
        return TEXT("vehicle_tire");
    }
    if (Part.Contains(TEXT("cab")))
    {
        return TEXT("vehicle_cab");
    }
    if (Part.Contains(TEXT("vehiclebody")))
    {
        return TEXT("vehicle_body");
    }
    if (Part.Contains(TEXT("direction")))
    {
        return TEXT("direction_marker");
    }
    if (Part.Contains(TEXT("riderhead")))
    {
        return TEXT("rider_skin");
    }
    if (Part.Contains(TEXT("rider")))
    {
        return TEXT("rider_clothing");
    }
    if (Part.Contains(TEXT("bike")))
    {
        return TEXT("bike_frame");
    }
    if (Part.Contains(TEXT("leg")))
    {
        return TEXT("animal_limb");
    }
    if (Part.Contains(TEXT("cowhead")) || Part.Contains(TEXT("cowbody")))
    {
        return TEXT("animal_body");
    }
    if (Part.Contains(TEXT("trunk")))
    {
        return TEXT("vegetation_trunk");
    }
    if (Part.Contains(TEXT("canopy")))
    {
        return TEXT("vegetation_canopy");
    }
    if (Part.Contains(TEXT("tower")))
    {
        return TEXT("vertical_structure_metal");
    }
    return TEXT("semantic_proxy_part");
}

FName APorceSemanticProxyActor::ResolveEvidenceSource() const
{
    return bCurrentProxyUsesFallback ? TEXT("fallback_unknown") : TEXT("semantic_prior");
}

FName APorceSemanticProxyActor::ResolveUncertaintyStyle(const FName& MaterialRole) const
{
    if (bCurrentProxyUsesFallback)
    {
        return MaterialRole == TEXT("uncertainty_marker") ? TEXT("warning_marker") : TEXT("desaturated_unknown");
    }
    return CurrentConfidenceAlpha < 0.50f ? TEXT("low_confidence_desaturation") : TEXT("none");
}

bool APorceSemanticProxyActor::TryInferDescriptorReferenceDimsM(FVector& OutDimsM) const
{
    if (DescriptorMetersToCentimeters <= KINDA_SMALL_NUMBER)
    {
        return false;
    }

    FBox LocalBounds(ForceInit);
    for (const UStaticMeshComponent* Component : GeneratedComponents)
    {
        if (!IsValid(Component) || !IsValid(Component->GetStaticMesh()))
        {
            continue;
        }

        const FBox MeshBounds = Component->GetStaticMesh()->GetBoundingBox();
        if (!MeshBounds.IsValid)
        {
            continue;
        }
        LocalBounds += MeshBounds.TransformBy(Component->GetRelativeTransform());
    }

    if (!LocalBounds.IsValid)
    {
        return false;
    }

    const FVector SizeCm = LocalBounds.GetSize();
    if (SizeCm.X <= KINDA_SMALL_NUMBER || SizeCm.Y <= KINDA_SMALL_NUMBER || SizeCm.Z <= KINDA_SMALL_NUMBER)
    {
        return false;
    }

    OutDimsM = SizeCm / DescriptorMetersToCentimeters;
    return FMath::IsFinite(OutDimsM.X) && FMath::IsFinite(OutDimsM.Y) && FMath::IsFinite(OutDimsM.Z);
}

FLinearColor APorceSemanticProxyActor::ResolvePartColor(const FName& PartName, const FLinearColor& BaseColor) const
{
    if (!bUseEvidenceCalibratedMaterials)
    {
        return BaseColor;
    }

    const FName MaterialRole = ResolveMaterialRole(PartName);
    FLinearColor Color = BaseColor;
    if (bCurrentProxyUsesFallback)
    {
        if (MaterialRole == TEXT("uncertainty_marker"))
        {
            Color = FLinearColor(0.95f, 0.72f, 0.06f, 1.0f);
        }
        else if (MaterialRole == TEXT("unknown_footprint"))
        {
            Color = FLinearColor(0.38f, 0.38f, 0.40f, 1.0f);
        }
        else
        {
            Color = FLinearColor(0.55f, 0.55f, 0.58f, 1.0f);
        }
    }
    else if (MaterialRole == TEXT("vehicle_tire"))
    {
        Color = FLinearColor(0.02f, 0.02f, 0.02f, 1.0f);
    }
    else if (MaterialRole == TEXT("vehicle_cab"))
    {
        Color = FLinearColor(0.05f, 0.18f, 0.75f, 1.0f);
    }
    else if (MaterialRole == TEXT("vehicle_body"))
    {
        Color = FLinearColor(0.70f, 0.05f, 0.04f, 1.0f);
    }
    else if (MaterialRole == TEXT("vehicle_metal_or_hub") || MaterialRole == TEXT("vertical_structure_metal"))
    {
        Color = FLinearColor(0.62f, 0.62f, 0.60f, 1.0f);
    }
    else if (MaterialRole == TEXT("direction_marker") || MaterialRole == TEXT("bike_frame"))
    {
        Color = FLinearColor(0.95f, 0.72f, 0.06f, 1.0f);
    }
    else if (MaterialRole == TEXT("rider_clothing"))
    {
        Color = FLinearColor(0.05f, 0.18f, 0.75f, 1.0f);
    }
    else if (MaterialRole == TEXT("rider_skin"))
    {
        Color = FLinearColor(0.85f, 0.75f, 0.55f, 1.0f);
    }
    else if (MaterialRole == TEXT("animal_limb"))
    {
        Color = FLinearColor(0.20f, 0.10f, 0.04f, 1.0f);
    }
    else if (MaterialRole == TEXT("animal_body"))
    {
        Color = FLinearColor(0.92f, 0.92f, 0.86f, 1.0f);
    }
    else if (MaterialRole == TEXT("vegetation_trunk"))
    {
        Color = FLinearColor(0.45f, 0.25f, 0.10f, 1.0f);
    }
    else if (MaterialRole == TEXT("vegetation_canopy"))
    {
        Color = FLinearColor(0.10f, 0.55f, 0.16f, 1.0f);
    }

    if (!bCurrentProxyUsesFallback && CurrentConfidenceAlpha < 0.50f)
    {
        const float Desaturate = FMath::Clamp((0.50f - CurrentConfidenceAlpha) * 1.2f, 0.0f, 0.45f);
        Color.R = FMath::Lerp(Color.R, 0.55f, Desaturate);
        Color.G = FMath::Lerp(Color.G, 0.55f, Desaturate);
        Color.B = FMath::Lerp(Color.B, 0.55f, Desaturate);
    }
    Color.A = bCurrentProxyUsesFallback ? FMath::Lerp(0.45f, 0.85f, CurrentConfidenceAlpha) : FMath::Lerp(0.55f, 1.0f, CurrentConfidenceAlpha);
    return Color;
}

FLinearColor APorceSemanticProxyActor::ResolveMaterialColor(const FName& MaterialRole, const FName& EvidenceSource, const FName& UncertaintyStyle, const FLinearColor& BaseColor) const
{
    if (!bUseEvidenceCalibratedMaterials)
    {
        return BaseColor;
    }

    FLinearColor Color = BaseColor;
    if (EvidenceSource == TEXT("fallback_unknown"))
    {
        if (MaterialRole == TEXT("uncertainty_marker") || UncertaintyStyle == TEXT("warning_marker"))
        {
            Color = FLinearColor(0.95f, 0.72f, 0.06f, 1.0f);
        }
        else if (MaterialRole == TEXT("unknown_footprint"))
        {
            Color = FLinearColor(0.38f, 0.38f, 0.40f, 1.0f);
        }
        else
        {
            Color = FLinearColor(0.55f, 0.55f, 0.58f, 1.0f);
        }
    }
    else if (MaterialRole == TEXT("vehicle_tire"))
    {
        Color = FLinearColor(0.02f, 0.02f, 0.02f, 1.0f);
    }
    else if (MaterialRole == TEXT("vehicle_cab"))
    {
        Color = FLinearColor(0.05f, 0.18f, 0.75f, 1.0f);
    }
    else if (MaterialRole == TEXT("vehicle_body") || MaterialRole == TEXT("vehicle_attachment"))
    {
        Color = FLinearColor(0.70f, 0.05f, 0.04f, 1.0f);
    }
    else if (MaterialRole == TEXT("vehicle_window"))
    {
        Color = FLinearColor(0.08f, 0.25f, 0.55f, 0.82f);
    }
    else if (MaterialRole == TEXT("vehicle_metal_or_hub") || MaterialRole == TEXT("vertical_structure_metal"))
    {
        Color = FLinearColor(0.62f, 0.62f, 0.60f, 1.0f);
    }
    else if (MaterialRole == TEXT("direction_marker") || MaterialRole == TEXT("bike_frame"))
    {
        Color = FLinearColor(0.95f, 0.72f, 0.06f, 1.0f);
    }
    else if (MaterialRole == TEXT("rider_clothing"))
    {
        Color = FLinearColor(0.05f, 0.18f, 0.75f, 1.0f);
    }
    else if (MaterialRole == TEXT("rider_skin") || MaterialRole == TEXT("animal_skin_or_horn"))
    {
        Color = FLinearColor(0.85f, 0.75f, 0.55f, 1.0f);
    }
    else if (MaterialRole == TEXT("animal_limb"))
    {
        Color = FLinearColor(0.20f, 0.10f, 0.04f, 1.0f);
    }
    else if (MaterialRole == TEXT("animal_body"))
    {
        Color = FLinearColor(0.92f, 0.92f, 0.86f, 1.0f);
    }
    else if (MaterialRole == TEXT("animal_marking"))
    {
        Color = FLinearColor(0.12f, 0.08f, 0.05f, 1.0f);
    }
    else if (MaterialRole == TEXT("vegetation_trunk"))
    {
        Color = FLinearColor(0.45f, 0.25f, 0.10f, 1.0f);
    }
    else if (MaterialRole == TEXT("vegetation_canopy"))
    {
        Color = FLinearColor(0.10f, 0.55f, 0.16f, 1.0f);
    }

    if (UncertaintyStyle == TEXT("low_confidence_desaturation"))
    {
        const float Desaturate = FMath::Clamp((0.50f - CurrentConfidenceAlpha) * 1.2f, 0.0f, 0.45f);
        Color.R = FMath::Lerp(Color.R, 0.55f, Desaturate);
        Color.G = FMath::Lerp(Color.G, 0.55f, Desaturate);
        Color.B = FMath::Lerp(Color.B, 0.55f, Desaturate);
    }
    Color.A = EvidenceSource == TEXT("fallback_unknown")
        ? FMath::Lerp(0.45f, 0.85f, CurrentConfidenceAlpha)
        : FMath::Lerp(0.55f, 1.0f, CurrentConfidenceAlpha);
    return Color;
}

UStaticMeshComponent* APorceSemanticProxyActor::AddPart(
    const FName& ShapeName,
    const FName& PartName,
    const FVector& RelativeLocation,
    const FRotator& RelativeRotation,
    const FVector& RelativeScale,
    const FLinearColor& Color,
    bool bConfirmed,
    const FName& ExplicitMaterialRole,
    const FName& ExplicitEvidenceSource,
    const FName& ExplicitUncertaintyStyle
)
{
    UStaticMesh* Mesh = ResolveMesh(ShapeName);
    if (!IsValid(Mesh))
    {
        return nullptr;
    }

    const FName ComponentName = MakeUniqueObjectName(this, UStaticMeshComponent::StaticClass(), PartName);
    UStaticMeshComponent* Component = NewObject<UStaticMeshComponent>(this, ComponentName);
    if (!IsValid(Component))
    {
        return nullptr;
    }

    Component->SetupAttachment(ProxyRoot);
    Component->SetStaticMesh(Mesh);
    Component->SetRelativeLocation(RelativeLocation);
    Component->SetRelativeRotation(RelativeRotation);
    Component->SetRelativeScale3D(RelativeScale);
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetCollisionEnabled((bConfirmed && bEnableCollisionForConfirmed) ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
    Component->SetGenerateOverlapEvents(false);

    const FName MaterialRole = ExplicitMaterialRole.IsNone() ? ResolveMaterialRole(PartName) : ExplicitMaterialRole;
    const FName EvidenceSource = ExplicitEvidenceSource.IsNone() ? ResolveEvidenceSource() : ExplicitEvidenceSource;
    const FName UncertaintyStyle = ExplicitUncertaintyStyle.IsNone() ? ResolveUncertaintyStyle(MaterialRole) : ExplicitUncertaintyStyle;
    const FLinearColor DisplayColor = ExplicitMaterialRole.IsNone()
        ? ResolvePartColor(PartName, Color)
        : ResolveMaterialColor(MaterialRole, EvidenceSource, UncertaintyStyle, Color);

    const FName MaterialRoleTag(*FString::Printf(TEXT("SPPA_MATERIAL_ROLE_%s"), *MaterialRole.ToString()));
    const FName EvidenceSourceTag(*FString::Printf(TEXT("SPPA_EVIDENCE_SOURCE_%s"), *EvidenceSource.ToString()));
    const FName UncertaintyStyleTag(*FString::Printf(TEXT("SPPA_UNCERTAINTY_STYLE_%s"), *UncertaintyStyle.ToString()));
    Component->ComponentTags.AddUnique(MaterialRoleTag);
    Component->ComponentTags.AddUnique(EvidenceSourceTag);
    Component->ComponentTags.AddUnique(UncertaintyStyleTag);

    if (IsValid(BasicShapeMaterial))
    {
        UMaterialInstanceDynamic* DynamicMaterial = UMaterialInstanceDynamic::Create(BasicShapeMaterial, this);
        if (IsValid(DynamicMaterial))
        {
            DynamicMaterial->SetVectorParameterValue(TEXT("Color"), DisplayColor);
            DynamicMaterial->SetScalarParameterValue(TEXT("SPPAConfidence"), CurrentConfidenceAlpha);
            DynamicMaterial->SetScalarParameterValue(TEXT("SPPAEvidenceSource"), bCurrentProxyUsesFallback ? 2.0f : 1.0f);
            DynamicMaterial->SetScalarParameterValue(TEXT("SPPAUncertaintyStyle"), UncertaintyStyle == TEXT("none") ? 0.0f : (UncertaintyStyle == TEXT("low_confidence_desaturation") ? 1.0f : (UncertaintyStyle == TEXT("desaturated_unknown") ? 2.0f : 3.0f)));
            Component->SetMaterial(0, DynamicMaterial);
        }
        else
        {
            Component->SetMaterial(0, BasicShapeMaterial);
        }
    }

    Component->RegisterComponent();
    AddInstanceComponent(Component);
    GeneratedComponents.Add(Component);
    return Component;
}

void APorceSemanticProxyActor::BuildBikerProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cylinder"), TEXT("WheelFront"), FVector(48.0f, 0.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.32f), Color, bConfirmed);
    AddPart(TEXT("cylinder"), TEXT("WheelRear"), FVector(-48.0f, 0.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.32f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("BikeFrame"), FVector(0.0f, 0.0f, 82.0f), FRotator(0.0f, 0.0f, 0.0f), FVector(1.05f, 0.10f, 0.10f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("BikeFork"), FVector(34.0f, 0.0f, 90.0f), FRotator(0.0f, 0.0f, -32.0f), FVector(0.12f, 0.10f, 0.70f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("RiderBody"), FVector(0.0f, 0.0f, 150.0f), FRotator(0.0f, 0.0f, -10.0f), FVector(0.28f, 0.20f, 0.82f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("RiderHead"), FVector(10.0f, 0.0f, 205.0f), FRotator::ZeroRotator, FVector(0.24f, 0.24f, 0.24f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildCowProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("sphere"), TEXT("CowBody"), FVector(0.0f, 0.0f, 95.0f), FRotator::ZeroRotator, FVector(0.92f, 0.42f, 0.38f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("CowHead"), FVector(78.0f, 0.0f, 120.0f), FRotator::ZeroRotator, FVector(0.30f, 0.24f, 0.26f), Color, bConfirmed);
    AddPart(TEXT("cone"), TEXT("CowDirection"), FVector(112.0f, 0.0f, 122.0f), FRotator(0.0f, 90.0f, 0.0f), FVector(0.18f, 0.18f, 0.30f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegFL"), FVector(42.0f, 20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegFR"), FVector(42.0f, -20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegRL"), FVector(-42.0f, 20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("LegRR"), FVector(-42.0f, -20.0f, 48.0f), FRotator::ZeroRotator, FVector(0.10f, 0.10f, 0.55f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildVehicleProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cube"), TEXT("VehicleBody"), FVector(0.0f, 0.0f, 82.0f), FRotator::ZeroRotator, FVector(1.35f, 0.46f, 0.34f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("VehicleCab"), FVector(44.0f, 0.0f, 125.0f), FRotator::ZeroRotator, FVector(0.48f, 0.40f, 0.38f), Color, bConfirmed);
    AddPart(TEXT("cylinder"), TEXT("WheelFrontLeft"), FVector(55.0f, 46.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.24f), Color, bConfirmed);
    AddPart(TEXT("cylinder"), TEXT("WheelFrontRight"), FVector(55.0f, -46.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.24f), Color, bConfirmed);
    AddPart(TEXT("cylinder"), TEXT("WheelRearLeft"), FVector(-55.0f, 46.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.24f), Color, bConfirmed);
    AddPart(TEXT("cylinder"), TEXT("WheelRearRight"), FVector(-55.0f, -46.0f, 42.0f), FRotator(0.0f, 0.0f, 90.0f), FVector(0.08f, 0.08f, 0.24f), Color, bConfirmed);
    AddPart(TEXT("cone"), TEXT("VehicleDirection"), FVector(104.0f, 0.0f, 92.0f), FRotator(0.0f, 90.0f, 0.0f), FVector(0.18f, 0.18f, 0.30f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildVegetationProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cylinder"), TEXT("VegetationTrunk"), FVector(0.0f, 0.0f, 85.0f), FRotator::ZeroRotator, FVector(0.16f, 0.16f, 1.70f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("CanopyLower"), FVector(0.0f, 0.0f, 185.0f), FRotator::ZeroRotator, FVector(0.72f, 0.64f, 0.46f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("CanopyLeft"), FVector(-38.0f, 16.0f, 220.0f), FRotator::ZeroRotator, FVector(0.46f, 0.40f, 0.36f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("CanopyRight"), FVector(38.0f, -16.0f, 220.0f), FRotator::ZeroRotator, FVector(0.46f, 0.40f, 0.36f), Color, bConfirmed);
    AddPart(TEXT("sphere"), TEXT("CanopyTop"), FVector(0.0f, 0.0f, 255.0f), FRotator::ZeroRotator, FVector(0.40f, 0.36f, 0.34f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildTowerProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cylinder"), TEXT("TowerMast"), FVector(0.0f, 0.0f, 210.0f), FRotator::ZeroRotator, FVector(0.22f, 0.22f, 4.20f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("TowerTopCrossbar"), FVector(0.0f, 0.0f, 430.0f), FRotator::ZeroRotator, FVector(1.70f, 0.12f, 0.12f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("TowerMidCrossbar"), FVector(0.0f, 0.0f, 310.0f), FRotator::ZeroRotator, FVector(1.30f, 0.10f, 0.10f), Color, bConfirmed);
    AddPart(TEXT("cone"), TEXT("TowerApex"), FVector(0.0f, 0.0f, 480.0f), FRotator::ZeroRotator, FVector(0.55f, 0.55f, 0.75f), Color, bConfirmed);
}

void APorceSemanticProxyActor::BuildUnknownProxy(const FLinearColor& Color, bool bConfirmed)
{
    AddPart(TEXT("cylinder"), TEXT("UnknownFootprint"), FVector(0.0f, 0.0f, 18.0f), FRotator::ZeroRotator, FVector(0.75f, 0.75f, 0.12f), Color, bConfirmed);
    AddPart(TEXT("cube"), TEXT("UnknownVolume"), FVector(0.0f, 0.0f, 82.0f), FRotator::ZeroRotator, FVector(0.70f, 0.70f, 1.10f), Color, bConfirmed);
    AddPart(TEXT("cone"), TEXT("UnknownUncertainty"), FVector(0.0f, 0.0f, 158.0f), FRotator::ZeroRotator, FVector(0.42f, 0.42f, 0.52f), Color, bConfirmed);
}
