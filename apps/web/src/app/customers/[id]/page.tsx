export default async function CustomerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="text-2xl font-semibold">Customer details</h1>
      <p className="mt-2 text-sm text-muted-foreground">Customer id: {id}. Placeholder. Not built yet.</p>
    </main>
  );
}
