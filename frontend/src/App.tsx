import { useState, useEffect } from 'react';
import { Shield, Search, AlertTriangle, AlertCircle, CheckCircle, Activity, Globe, Clock, ShieldCheck } from 'lucide-react';

interface APIResponse {
  data: {
    image_url: string;
    image_urls: string[];
    image_index: number | null;
    seller_location: string;
    source_url: string;
    title: string;
  };
  identity_guard: {
    classification: string;
    forensic_notes: string;
    match_confidence: number;
  } | null;
  identity_guard_error: string | null;
  scam_signals: {
    duplicates: Array<{ title: string; url: string }>;
    geographic_conflicts: Array<{ host: string; title: string; tld: string; url: string }>;
    temporal_conflicts: Array<{ matched_text: string; title: string; url: string; year: string }>;
  };
  serpapi: {
    configured: boolean;
    error: string | null;
    skipped: boolean;
  };
}

const LOADING_STEPS = [
  "Targeting eBay URL...",
  "Extracting listing data and images...",
  "Scanning Google Lens database...",
  "Running AI mechanical identity inspection...",
  "Finalizing forensic report..."
];

export default function App() {
  const [url, setUrl] = useState('');
  const [imageIndex, setImageIndex] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [result, setResult] = useState<APIResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (loading) {
      interval = setInterval(() => {
        setLoadingStage((prev) => Math.min(prev + 1, LOADING_STEPS.length - 1));
      }, 1800);
    }
    return () => clearInterval(interval);
  }, [loading]);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setLoadingStage(0);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('http://127.0.0.1:5000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, image_index: imageIndex }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to analyze listing.');
      }

      setResult(data);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const getIdentityGuardTheme = (classification: string | undefined) => {
    switch (classification) {
      case 'exact_match':
        return {
          cardBg: 'bg-green-950/20 border-green-500/30',
          text: 'text-green-400',
          icon: <ShieldCheck className="w-8 h-8 text-green-400" />,
          label: 'Exact Match',
        };
      case 'generic_stock_photo':
        return {
          cardBg: 'bg-yellow-950/20 border-yellow-500/30',
          text: 'text-yellow-400',
          icon: <AlertTriangle className="w-8 h-8 text-yellow-400" />,
          label: 'Stock Photo',
        };
      case 'misidentified_part':
      case 'mismatched_condition':
        return {
          cardBg: 'bg-red-950/20 border-red-500/30',
          text: 'text-red-400',
          icon: <AlertCircle className="w-8 h-8 text-red-500" />,
          label: classification === 'misidentified_part' ? 'Misidentified Part' : 'Condition Mismatch',
        };
      default:
        return {
          cardBg: 'bg-gray-800/50 border-gray-700',
          text: 'text-gray-400',
          icon: <Shield className="w-8 h-8 text-gray-400" />,
          label: 'Unknown',
        };
    }
  };

  return (
    <div className="min-h-screen font-sans">
      <header className="border-b border-gray-800/60 bg-gray-900/50 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-blue-600/20 p-2 rounded-lg border border-blue-500/30">
              <Shield className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-gray-100">BrumBuster</h1>
              <p className="text-xs text-blue-400/80 font-medium uppercase tracking-wider">Ebay Car Parts Visual Forensics</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        <section className="text-center space-y-6 max-w-2xl mx-auto">
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-gray-100 to-gray-500">
            Verify before you buy.
          </h2>
          <p className="text-lg text-gray-400">
            Paste an eBay UK car part listing below. We'll cross-reference the image against the mechanical description and global lens databases to flag scams and stock photos.
          </p>

          <form onSubmit={handleAnalyze} className="relative mt-8">
            <div className="flex items-center bg-gray-900 border border-gray-700/60 rounded-xl overflow-hidden shadow-2xl transition-all focus-within:border-blue-500/50 focus-within:ring-2 focus-within:ring-blue-500/20">
              <div className="pl-4 text-gray-500">
                <Search className="w-6 h-6" />
              </div>
              <input
                type="url"
                required
                placeholder="https://www.ebay.co.uk/itm/155129602757"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={loading}
                className="w-full bg-transparent border-none text-gray-100 px-4 py-5 focus:outline-none placeholder-gray-600 text-lg"
              />
              <div className="border-l border-gray-700/60 pl-4 py-2 flex items-center shrink-0">
                <label htmlFor="image-index" className="text-gray-400 text-sm font-medium mr-2 whitespace-nowrap">Image #</label>
                <input
                  id="image-index"
                  type="number"
                  min="1"
                  value={imageIndex}
                  onChange={(e) => setImageIndex(parseInt(e.target.value) || 1)}
                  disabled={loading}
                  className="w-16 bg-gray-800 border border-gray-700 text-gray-100 px-2 py-1.5 rounded-lg focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 text-center mr-4"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !url.trim()}
                className="bg-blue-600 hover:bg-blue-500 transition-colors text-white font-semibold px-8 py-5 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {loading ? 'Scanning...' : 'Analyze Listing'}
              </button>
            </div>
          </form>
        </section>

        {loading && (
          <section className="bg-gray-900/60 border border-gray-800 rounded-2xl p-8 max-w-2xl mx-auto shadow-xl">
            <div className="flex items-center mb-6 space-x-3">
              <Activity className="w-5 h-5 text-blue-400 animate-pulse" />
              <h3 className="text-lg font-semibold text-gray-200">Live Analysis Status</h3>
            </div>
            <div className="space-y-4">
              {LOADING_STEPS.map((step, idx) => {
                const isCompleted = idx < loadingStage;
                const isActive = idx === loadingStage;
                return (
                  <div key={idx} className="flex items-center space-x-4">
                    {isCompleted ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : isActive ? (
                      <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <div className="w-5 h-5 border-2 border-gray-700 rounded-full" />
                    )}
                    <span className={`text-sm font-medium ${isCompleted ? 'text-gray-400' : isActive ? 'text-blue-400 animate-blink' : 'text-gray-600'}`}>
                      {step}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {error && (
          <div className="bg-red-950/30 border border-red-500/30 p-6 rounded-xl max-w-2xl mx-auto flex items-start space-x-4">
            <AlertCircle className="w-6 h-6 text-red-500 shrink-0 mt-0.5" />
            <div>
              <h3 className="text-red-400 font-semibold mb-1">Analysis Failed</h3>
              <p className="text-red-400/80 text-sm">{error}</p>
            </div>
          </div>
        )}

        {result && !loading && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Listing Overview */}
            <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row gap-6">
              <div className="w-full md:w-1/3 aspect-square bg-gray-800 rounded-xl overflow-hidden border border-gray-700">
                {result.data.image_url ? (
                  <img src={result.data.image_url} alt="Listing" className="w-full h-full object-contain mix-blend-luminosity p-2" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-600">No Image</div>
                )}
              </div>
              <div className="flex-1 space-y-4 pt-2">
                <div>
                  <h3 className="text-xl font-bold text-gray-100 leading-snug">{result.data.title || 'Unknown Title'}</h3>
                  <a href={result.data.source_url} target="_blank" rel="noreferrer" className="text-blue-400 text-sm hover:underline mt-2 inline-block">
                    View Original Listing ↗
                  </a>
                </div>
                <div className="flex items-center text-gray-400 text-sm bg-gray-800/50 inline-flex px-3 py-1.5 rounded-lg border border-gray-700">
                  <Globe className="w-4 h-4 mr-2" />
                  {result.data.seller_location || 'Location Unknown'}
                </div>
              </div>
            </section>

            <div className="flex flex-col gap-8">
              {/* Identity Guard Card */}
              <section className={`border rounded-2xl p-6 shadow-xl flex flex-col ${getIdentityGuardTheme(result.identity_guard?.classification).cardBg}`}>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center space-x-3">
                    {getIdentityGuardTheme(result.identity_guard?.classification).icon}
                    <h3 className="text-xl font-bold text-gray-100">Match Verification</h3>
                  </div>
                  {result.identity_guard && (
                    <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-black/40 border border-current ${getIdentityGuardTheme(result.identity_guard.classification).text}`}>
                      {getIdentityGuardTheme(result.identity_guard.classification).label}
                    </span>
                  )}
                </div>

                {result.identity_guard ? (
                  <div className="space-y-6 flex-1">
                    <div>
                      <div className="flex justify-between text-sm mb-2">
                        <span className="text-gray-400 font-medium">Confidence Score</span>
                        <span className={getIdentityGuardTheme(result.identity_guard.classification).text + " font-bold"}>
                          {Math.round(result.identity_guard.match_confidence * 100)}%
                        </span>
                      </div>
                      <div className="h-2.5 w-full bg-gray-900 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full transition-all duration-1000 ${
                            result.identity_guard.classification === 'exact_match' ? 'bg-green-500' : 
                            result.identity_guard.classification === 'generic_stock_photo' ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.round(result.identity_guard.match_confidence * 100)}%` }}
                        />
                      </div>
                    </div>
                    <div className="bg-black/20 p-4 rounded-xl border border-white/5">
                      <p className="text-gray-300 text-sm leading-relaxed">
                        {result.identity_guard.forensic_notes}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center space-y-3 py-8 text-center bg-black/20 rounded-xl border border-white/5">
                    <Shield className="w-8 h-8 text-gray-600" />
                    <div>
                      <p className="text-gray-400 font-medium">Inspection Failed</p>
                      <p className="text-gray-500 text-sm">{result.identity_guard_error || 'Could not verify identity.'}</p>
                    </div>
                  </div>
                )}
              </section>

              {/* Ghost Tracker Card */}
              <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col">
                <div className="flex items-center space-x-3 mb-6">
                  <div className="bg-purple-500/20 p-2 rounded-lg border border-purple-500/30">
                    <Search className="w-6 h-6 text-purple-400" />
                  </div>
                  <h3 className="text-xl font-bold text-gray-100">Duplicates & Conflicts</h3>
                </div>

                <div className="space-y-8 flex-1 pr-2">
                  {/* Regular Duplicates */}
                  {result.scam_signals.duplicates.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                        Active eBay Clones ({result.scam_signals.duplicates.length})
                      </h4>
                      <div className="bg-black/20 border border-gray-800/60 rounded-xl p-3 shadow-inner">
                        <div className="space-y-2 max-h-[156px] overflow-y-auto pr-2 custom-scrollbar">
                          {result.scam_signals.duplicates.map((item, i) => (
                            <a key={i} href={item.url} target="_blank" rel="noreferrer" className="block bg-gray-800/80 hover:bg-gray-700/80 transition-colors border border-gray-700/50 p-3 rounded-lg group text-sm text-gray-300 truncate">
                              {item.title}
                            </a>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Conflict Logs */}
                  {(result.scam_signals.geographic_conflicts.length > 0 || result.scam_signals.temporal_conflicts.length > 0) && (
                    <div className={`grid grid-cols-1 ${
                      result.scam_signals.geographic_conflicts.length > 0 && result.scam_signals.temporal_conflicts.length > 0 
                        ? 'md:grid-cols-2' 
                        : 'max-w-2xl mx-auto w-full'
                    } gap-6`}>
                      
                      {/* Geographic Conflicts */}
                      {result.scam_signals.geographic_conflicts.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider flex items-center">
                            <AlertTriangle className="w-4 h-4 mr-2 text-orange-400" /> 
                            Geographic Conflicts
                          </h4>
                          {result.scam_signals.geographic_conflicts.slice(0, 3).map((item, i) => (
                            <div key={i} className="bg-orange-950/20 border border-orange-500/20 p-3 rounded-xl flex items-start space-x-3">
                              <Globe className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
                              <div className="min-w-0">
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-400 mb-1 border border-orange-500/30">
                                  .{item.tld.toUpperCase()} Domain
                                </span>
                                <p className="text-sm text-gray-300 truncate">{item.title}</p>
                                <a href={item.url} target="_blank" rel="noreferrer" className="text-xs text-orange-400/80 hover:underline truncate block">
                                  {item.host}
                                </a>
                              </div>
                            </div>
                          ))}
                          {result.scam_signals.geographic_conflicts.length > 3 && (
                            <div className="text-xs text-gray-500 text-center pt-2">
                              + {result.scam_signals.geographic_conflicts.length - 3} more conflicts
                            </div>
                          )}
                        </div>
                      )}

                      {/* Temporal Conflicts */}
                      {result.scam_signals.temporal_conflicts.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider flex items-center">
                            <Clock className="w-4 h-4 mr-2 text-rose-400" /> 
                            Temporal Conflicts
                          </h4>
                          {result.scam_signals.temporal_conflicts.slice(0, 3).map((item, i) => (
                            <div key={i} className="bg-rose-950/20 border border-rose-500/20 p-3 rounded-xl flex items-start space-x-3">
                              <Clock className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                              <div className="min-w-0">
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 mb-1 border border-rose-500/30">
                                  {item.year ? `From ${item.year}` : 'Old Origin'}
                                </span>
                                <p className="text-sm text-gray-300 truncate">{item.title}</p>
                              </div>
                            </div>
                          ))}
                          {result.scam_signals.temporal_conflicts.length > 3 && (
                            <div className="text-xs text-gray-500 text-center pt-2">
                              + {result.scam_signals.temporal_conflicts.length - 3} more conflicts
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {result.scam_signals.geographic_conflicts.length === 0 && 
                   result.scam_signals.temporal_conflicts.length === 0 && 
                   result.scam_signals.duplicates.length === 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center space-y-3 py-8 text-center">
                      <CheckCircle className="w-8 h-8 text-green-500/50" />
                      <div>
                        {result.identity_guard?.classification === 'generic_stock_photo' ? (
                          <>
                            <p className="text-gray-400 font-medium">Visual duplicates hidden</p>
                            <p className="text-gray-500 text-sm">Harmless manufacturer stock asset verified.</p>
                          </>
                        ) : (
                          <>
                            <p className="text-gray-400 font-medium">No Duplicates or Conflicts Detected</p>
                            <p className="text-gray-500 text-sm">Image appears unique to this listing.</p>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
