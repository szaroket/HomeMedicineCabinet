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

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    reset,
    formState: { errors },
  } = useForm<AddEntryValues>({ resolver: zodResolver(addEntrySchema) });

  function handleProductSelect(p: ProductOut) {
    setSelectedProduct(p);
    setSelectedVariant(null);
    setValue("medication_registry_id", "");
  }

  function handleVariantChange(v: VariantOut) {
    setSelectedVariant(v);
    setValue("medication_registry_id", v.id);
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

    setServerError(null);
    mutate(
      {
        medication_registry_id: values.medication_registry_id,
        package_count: values.package_count,
        expiry_date: values.expiry_date,
        partial_tablet_count: selectedVariant.is_tablet_based
          ? (values.partial_tablet_count ?? null)
          : null,
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
          selected={selectedProduct}
          onSelect={handleProductSelect}
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
          <label className="text-sm font-medium text-blue-400">
            Liczba opakowań
          </label>
          <input
            type="number"
            min={1}
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
                setValueAs: (v: string) =>
                  v === "" || v == null ? null : Number(v),
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
          <label className="text-sm font-medium text-blue-400">
            Termin ważności
          </label>
          <input
            type="date"
            className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            {...register("expiry_date")}
          />
          {errors.expiry_date && (
            <p className="text-xs text-red-400">{errors.expiry_date.message}</p>
          )}
        </div>

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
