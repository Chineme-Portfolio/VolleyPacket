import type { Metadata } from "next";
import Link from "next/link";
import { getAllPosts } from "@/lib/blog";

const SITE_URL = "https://volleypacket.com";

export const metadata: Metadata = {
  title: "Blog — VolleyPacket",
  description:
    "Practical guides on bulk email sending, batch PDF generation, mail merge, and document automation. Tips and tutorials from the VolleyPacket team.",
  keywords: [
    "bulk email guide",
    "batch PDF generation tutorial",
    "mail merge tips",
    "document automation blog",
    "VolleyPacket blog",
  ],
  alternates: {
    canonical: "/blog",
  },
  openGraph: {
    type: "website",
    url: `${SITE_URL}/blog`,
    title: "Blog — VolleyPacket",
    description:
      "Practical guides on bulk email sending, batch PDF generation, mail merge, and document automation.",
    siteName: "VolleyPacket",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "VolleyPacket Blog",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Blog — VolleyPacket",
    description:
      "Practical guides on bulk email sending, batch PDF generation, mail merge, and document automation.",
    images: ["/og-image.png"],
  },
};

export default function BlogListingPage() {
  const posts = getAllPosts();

  return (
    <div className="bg-white min-h-screen">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-white/80 border-b border-gray-100">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 h-16">
          <Link href="/" className="text-xl font-bold text-gray-900">
            VolleyPacket
          </Link>
          <div className="flex items-center gap-6 text-sm font-medium text-gray-600">
            <Link href="/" className="hover:text-gray-900 transition-colors">
              Home
            </Link>
            <Link
              href="/blog"
              className="text-green-800 font-semibold transition-colors"
            >
              Blog
            </Link>
            <Link
              href="/signup"
              className="px-5 py-2 bg-green-800 text-white font-semibold rounded-full hover:bg-green-900 transition-colors shadow-sm"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Header */}
      <header className="py-16 md:py-24 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <span className="text-sm font-semibold text-green-700 uppercase tracking-wider">
            Blog
          </span>
          <h1 className="text-4xl md:text-5xl font-extrabold text-gray-900 mt-3 tracking-tight">
            Guides &amp; Tutorials
          </h1>
          <p className="text-lg text-gray-500 mt-4 max-w-xl mx-auto leading-relaxed">
            Practical advice on batch emails, PDF generation, document
            automation, and working with data at scale.
          </p>
        </div>
      </header>

      {/* Posts grid */}
      <section className="max-w-4xl mx-auto px-6 pb-24">
        <div className="space-y-8">
          {posts.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="block group"
            >
              <article className="bg-white rounded-2xl border border-gray-100 shadow-sm p-7 hover:shadow-md transition-shadow">
                <div className="flex items-center gap-3 text-sm text-gray-400 mb-3">
                  <time dateTime={post.date}>
                    {new Date(post.date).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </time>
                  <span aria-hidden="true">&middot;</span>
                  <span>{post.readTime}</span>
                </div>
                <h2 className="text-xl md:text-2xl font-bold text-gray-900 group-hover:text-green-800 transition-colors leading-snug">
                  {post.title}
                </h2>
                <p className="text-gray-500 mt-3 leading-relaxed">
                  {post.excerpt}
                </p>
                <span className="inline-block mt-4 text-sm font-semibold text-green-700 group-hover:text-green-900 transition-colors">
                  Read article &rarr;
                </span>
              </article>
            </Link>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-6 text-center text-sm">
          &copy; {new Date().getFullYear()} VolleyPacket. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
