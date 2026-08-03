import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
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
    control,
    formState: { errors },
  } = useForm<AddEntryValues>({
    resolver: zodResolver(addEntrySchema),
    shouldUnregister: true,
  });

  // useWatch (not the watch() function) so React Compiler can memoize this
  // component instead of skipping it (react-hooks/incompatible-library).
  const isUsed = useWatch({ control, name: "isUsed" }) ?? false;

  function handleProductSelect(product: ProductOut) {
    setSelectedProduct(product);
    setSelectedVariant(null);
    setValue("medicationRegistryId", "");
  }

  function handleProductClear() {
    setSelectedProduct(null);
    setSelectedVariant(null);
    setValue("medicationRegistryId", "");
  }

  function handleVariantChange(variant: VariantOut) {
    setSelectedVariant(variant);
    setValue("medicationRegistryId", variant.id);
    setValue("isTabletBased", variant.isTabletBased);
  }

  function onSubmit(values: AddEntryValues) {
    if (!selectedVariant) return;

    if (selectedVariant.isTabletBased && values.partialTabletCount != null) {
      const tpp = selectedVariant.capacity ?? 0;
      if (values.partialTabletCount >= tpp) {
        setError("partialTabletCount", {
          type: "manual",
          message: `Częściowa liczba tabletek musi być mniejsza niż ${tpp}.`,
        });
        return;
      }
    }

    const usagePayload = values.isUsed
      ? {
          isUsed: true,
          dosageTimes: selectedVariant.isTabletBased
            ? (values.dosageTimes ?? null)
            : null,
          dosagePeriod: selectedVariant.isTabletBased
            ? (values.dosagePeriod ?? null)
            : null,
          dosageAmount: selectedVariant.isTabletBased
            ? (values.dosageAmount ?? null)
            : null,
          dosageStartDate: values.dosageStartDate || null,
          dosageEndDate: values.dosageEndDate || null,
        }
      : null;

    setServerError(null);
    mutate(
      {
        medicationRegistryId: values.medicationRegistryId,
        packageCount: values.packageCount,
        expiryDate: values.expiryDate,
        partialTabletCount: selectedVariant.isTabletBased
          ? (values.partialTabletCount ?? null)
          : null,
        isImportant: values.isImportant ?? false,
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

  const isTablet = selectedVariant?.isTabletBased ?? false;

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
        {errors.medicationRegistryId && (
          <p className="text-xs text-red-400">
            {errors.medicationRegistryId.message}
          </p>
        )}

        <div className="flex flex-col gap-1">
          <label
            htmlFor="packageCount"
            className="text-sm font-medium text-blue-400"
          >
            Liczba opakowań
          </label>
          <input
            id="packageCount"
            type="number"
            min={1}
            defaultValue={1}
            className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            {...register("packageCount", { valueAsNumber: true })}
          />
          {errors.packageCount && (
            <p className="text-xs text-red-400">
              {errors.packageCount.message}
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
              {...register("partialTabletCount", {
                setValueAs: (value: string) =>
                  value === "" || value == null ? null : Number(value),
              })}
            />
            <p className="text-xs text-slate-400">
              Ile tabletek pozostało w jednym otwartym opakowaniu (mniej niż{" "}
              {selectedVariant?.capacity ?? "?"} szt.).
            </p>
            {errors.partialTabletCount && (
              <p className="text-xs text-red-400">
                {errors.partialTabletCount.message}
              </p>
            )}
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label
            htmlFor="expiryDate"
            className="text-sm font-medium text-blue-400"
          >
            Termin ważności
          </label>
          <input
            id="expiryDate"
            type="date"
            className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            {...register("expiryDate")}
          />
          {errors.expiryDate && (
            <p className="text-xs text-red-400">{errors.expiryDate.message}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <input
            id="isImportant"
            type="checkbox"
            className="h-4 w-4 rounded border-slate-600 bg-slate-700 accent-blue-500"
            {...register("isImportant")}
          />
          <label
            htmlFor="isImportant"
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
