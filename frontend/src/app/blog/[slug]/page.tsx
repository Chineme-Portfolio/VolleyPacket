import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPostBySlug, getAllPosts } from "@/lib/blog";

const SITE_URL = "https://volleypacket.com";

interface PageProps {
  params: Promise<{ slug: string }>;
}

/* Generate static params for all blog posts */
export async function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slug }));
}

/* Dynamic metadata per post */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) return {};

  return {
    title: post.title,
    description: post.excerpt,
    keywords: post.keywords,
    alternates: {
      canonical: `/blog/${post.slug}`,
    },
    openGraph: {
      type: "article",
      url: `${SITE_URL}/blog/${post.slug}`,
      title: post.title,
      description: post.excerpt,
      siteName: "VolleyPacket",
      publishedTime: post.date,
      images: [
        {
          url: "/og-image.png",
          width: 1200,
          height: 630,
          alt: post.title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.excerpt,
      images: ["/og-image.png"],
    },
  };
}

/* ───── Simple markdown-to-HTML renderer ───── */
function renderMarkdown(md: string): string {
  return md
    .trim()
    .split("\n\n")
    .map((block) => {
      // Headings
      if (block.startsWith("## ")) {
        return `<h2 class="text-2xl font-bold text-gray-900 mt-10 mb-4">${block.slice(3)}</h2>`;
      }
      if (block.startsWith("### ")) {
        return `<h3 class="text-xl font-bold text-gray-900 mt-8 mb-3">${block.slice(4)}</h3>`;
      }

      // Unordered list
      if (block.match(/^[-*] /m)) {
        const items = block
          .split("\n")
          .filter((l) => l.match(/^[-*] /))
          .map((l) => `<li class="ml-4">${inlineFormat(l.replace(/^[-*] /, ""))}</li>`)
          .join("");
        return `<ul class="list-disc pl-6 space-y-1.5 text-gray-600 leading-relaxed">${items}</ul>`;
      }

      // Ordered list
      if (block.match(/^\d+\. /m)) {
        const items = block
          .split("\n")
          .filter((l) => l.match(/^\d+\. /))
          .map((l) => `<li class="ml-4">${inlineFormat(l.replace(/^\d+\. /, ""))}</li>`)
          .join("");
        return `<ol class="list-decimal pl-6 space-y-1.5 text-gray-600 leading-relaxed">${items}</ol>`;
      }

      // Regular paragraph
      return `<p class="text-gray-600 leading-relaxed">${inlineFormat(block.replace(/\n/g, " "))}</p>`;
    })
    .join("\n");
}

function inlineFormat(text: string): string {
  return (
    text
      // Bold
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-gray-900 font-semibold">$1</strong>')
      // Inline code
      .replace(/`(.+?)`/g, '<code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-green-800">$1</code>')
      // Links
      .replace(
        /\[(.+?)\]\((.+?)\)/g,
        '<a href="$2" class="text-green-700 underline hover:text-green-900">$1</a>'
      )
  );
}

/* ───── Blog post page ───── */
export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) notFound();

  const html = renderMarkdown(post.body);

  /* JSON-LD structured data for the article */
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.excerpt,
    datePublished: post.date,
    author: {
      "@type": "Organization",
      name: "VolleyPacket",
      url: SITE_URL,
    },
    publisher: {
      "@type": "Organization",
      name: "VolleyPacket",
      url: SITE_URL,
      logo: {
        "@type": "ImageObject",
        url: `${SITE_URL}/logo-full.png`,
      },
    },
    mainEntityOfPage: `${SITE_URL}/blog/${post.slug}`,
  };

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
              className="hover:text-gray-900 transition-colors"
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

      {/* Article header */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <header className="py-16 md:py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-3xl mx-auto px-6">
          <Link
            href="/blog"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-green-700 hover:text-green-900 transition-colors mb-8"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Back to Blog
          </Link>

          <div className="flex items-center gap-3 text-sm text-gray-400 mb-4">
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

          <h1 className="text-3xl md:text-4xl lg:text-5xl font-extrabold text-gray-900 leading-tight tracking-tight">
            {post.title}
          </h1>
          <p className="text-lg text-gray-500 mt-4 leading-relaxed">
            {post.excerpt}
          </p>
        </div>
      </header>

      {/* Article body */}
      <article className="max-w-3xl mx-auto px-6 pb-20">
        <div
          className="prose-custom space-y-5"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </article>

      {/* CTA banner */}
      <section className="py-16 bg-gradient-to-br from-green-800 to-green-950 text-white">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <h2 className="text-2xl md:text-3xl font-extrabold mb-4">
            Ready to automate your workflow?
          </h2>
          <p className="text-green-100 mb-8 leading-relaxed">
            VolleyPacket handles batch emails, PDF generation, and document
            automation so you can focus on what matters.
          </p>
          <Link
            href="/signup"
            className="inline-flex px-8 py-3.5 bg-white text-green-800 font-bold rounded-full hover:bg-green-50 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
          >
            Get Started for Free
          </Link>
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
