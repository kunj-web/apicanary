export default function LoadingMonitorDetails() {
  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl animate-pulse space-y-6">
        <div className="h-24 rounded-2xl bg-white" />
        <div className="grid gap-4 md:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-28 rounded-2xl bg-white" />
          ))}
        </div>
        <div className="h-80 rounded-2xl bg-white" />
      </div>
    </main>
  );
}
