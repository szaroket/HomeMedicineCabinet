import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { addEntrySchema } from "@/features/cabinet/schemas/cabinet-schemas";
import type { AddEntryValues } from "@/features/cabinet/schemas/cabinet-schemas";
import { useAddEntry } from "@/features/cabinet/api/cabinet-queries";
import type {
  ProductOut,
  VariantOut,
  AddEntryResult,
} from "@/features/cabinet/api/cabinet-api";
import { ProductAutocomplete } from "@/features/cabinet/components/product-autocomplete";
import { VariantSelect } from "@/features/cabinet/components/variant-select";
import { AddResultDialog } from "@/features/cabinet/components/add-result-dialog";
import { DosageFields } from "@/features/cabinet/components/dosage-fields";

export function AddMedicationForm() {
  const navigate = useNavigate();
  const { mutate, isPending } = useAddEntry();
  const [selectedProduct, setSelectedProduct] = useState<ProductOut | null>(
    null,
  );
  const [selectedVariant, setSelectedVariant] = useState<VariantOut | null>(
    null,
  );
  const [result, setResult] = useState<AddEntryResult | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    reset,
    watch,
    formState: { errors },
  } = useForm<AddEntryValues>({
    resolver: zodResolver(addEntrySchema),
    shouldUnregister: true,
  });

  const isUsed = watch("is_used") ?? false;

  function handleProductSelect(product: ProductOut) {
    setSelectedProduct(product);
    setSelectedVariant(null);
    setValue("medication_registry_id", "");
  }

  function handleProductClear() {
    setSelectedProduct(null);
    setSelectedVariant(null);
    setValue("medication_registry_id", "");
  }

  function handleVariantChange(variant: VariantOut) {
    setSelectedVariant(variant);
    setValue("medication_registry_id", variant.id);
    setValue("is_tablet_based", variant.is_tablet_based);
  }

  function onSubmit(values: AddEntryValues) {
    if (!selectedVariant) return;

    if (
      selectedVariant.is_tablet_based &&
      values.partial_tablet_count != null
    ) {
      const tpp = selectedVariant.capacity ?? 0;
      if (values.partial_tablet_count >= tpp) {
        setError("partial_tablet_count", {
          type: "manual",
          message: `Częściowa liczba tabletek musi być mniejsza niż ${tpp}.`,
        });
        return;
      }
    }

    const usagePayload = values.is_used
      ? {
          is_used: true,
          dosage_times: selectedVariant.is_tablet_based
            ? (values.dosage_times ?? null)
            : null,
          dosage_period: selectedVariant.is_tablet_based
            ? (values.dosage_period ?? null)
            : null,
          dosage_amount: selectedVariant.is_tablet_based
            ? (values.dosage_amount ?? null)
            : null,
          dosage_start_date: values.dosage_start_date || null,
          dosage_end_date: values.dosage_end_date || null,
        }
      : null;

    setServerError(null);
    mutate(
      {
        medication_registry_id: values.medication_registry_id,
        package_count: values.package_count,
        expiry_date: values.expiry_date,
        partial_tablet_count: selectedVariant.is_tablet_based
          ? (values.partial_tablet_count ?? null)
          : null,
        is_important: values.is_important ?? false,
        usage: usagePayload,
      },
      {
        onSuccess: (data) => setResult(data),
        onError: () =>
          setServerError("Wystąpił błąd. Sprawdź dane i spróbuj ponownie."),
      },
    );
  }

  function handleAddAnother() {
    setResult(null);
    setSelectedProduct(null);
    setSelectedVariant(null);
    reset();
    setFormKey((prev) => prev + 1);
  }

  function handleNavigate() {
    navigate("/cabinet");
  }

  const isTablet = selectedVariant?.is_tablet_based ?? false;

  return (
    <>
      {result && (
        <AddResultDialog
          result={result}
          onAddAnother={handleAddAnother}
          onNavigate={handleNavigate}
        />
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <ProductAutocomplete
          key={formKey}
          selected={selectedProduct}
          onSelect={handleProductSelect}
          onClear={handleProductClear}
        />

        <VariantSelect
          product={selectedProduct}
          selectedId={selectedVariant?.id ?? ""}
          onChange={handleVariantChange}
        />
        {errors.medication_registry_id && (
          <p className="text-xs text-red-400">
            {errors.medication_registry_id.message}
          </p>
        )}

        <div className="flex flex-col gap-1">
          <label
            htmlFor="package_count"
            className="text-sm font-medium text-blue-400"
          >
            Liczba opakowań
          </label>
          <input
            id="package_count"
            type="number"
            min={1}
            defaultValue={1}
            className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            {...register("package_count", { valueAsNumber: true })}
          />
          {errors.package_count && (
            <p className="text-xs text-red-400">
              {errors.package_count.message}
            </p>
          )}
        </div>

        {isTablet && (
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-blue-400">
              Liczba tabletek w otwartym opakowaniu
            </label>
            <input
              type="number"
              min={1}
              placeholder={`Opcjonalnie (1–${(selectedVariant?.capacity ?? 2) - 1} szt.)`}
              className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              {...register("partial_tablet_count", {
                setValueAs: (value: string) =>
                  value === "" || value == null ? null : Number(value),
              })}
            />
            <p className="text-xs text-slate-400">
              Ile tabletek pozostało w jednym otwartym opakowaniu (mniej niż{" "}
              {selectedVariant?.capacity ?? "?"} szt.).
            </p>
            {errors.partial_tablet_count && (
              <p className="text-xs text-red-400">
                {errors.partial_tablet_count.message}
              </p>
            )}
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label
            htmlFor="expiry_date"
            className="text-sm font-medium text-blue-400"
          >
            Termin ważności
          </label>
          <input
            id="expiry_date"
            type="date"
            className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            {...register("expiry_date")}
          />
          {errors.expiry_date && (
            <p className="text-xs text-red-400">{errors.expiry_date.message}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <input
            id="is_important"
            type="checkbox"
            className="h-4 w-4 rounded border-slate-600 bg-slate-700 accent-blue-500"
            {...register("is_important")}
          />
          <label
            htmlFor="is_important"
            className="cursor-pointer text-sm font-medium text-blue-400"
          >
            Oznacz jako ważny
          </label>
        </div>

        {selectedVariant && (
          <DosageFields
            isTabletBased={isTablet}
            isUsed={isUsed}
            register={register}
            errors={errors}
          />
        )}

        {serverError && <p className="text-sm text-red-400">{serverError}</p>}

        <button
          type="submit"
          disabled={isPending}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium uppercase tracking-wide text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {isPending ? "Dodawanie…" : "Dodaj do apteczki"}
        </button>
      </form>
    </>
  );
}
