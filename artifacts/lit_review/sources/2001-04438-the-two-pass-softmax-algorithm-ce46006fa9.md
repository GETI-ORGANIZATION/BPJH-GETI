 [2001.04438] The Two-Pass Softmax Algorithm






























  



[Skip to main content](#content)


[![Cornell University](/static/browse/0.3.4/images/icons/cu/cornell-reduced-white-SMALL.svg)](https://www.cornell.edu/)

[Learn about arXiv becoming an independent nonprofit.](https://tech.cornell.edu/arxiv/)

We gratefully acknowledge support from the Simons Foundation, [member institutions](https://info.arxiv.org/about/ourmembers.html), and all contributors.
[Donate](https://info.arxiv.org/about/donate.html)

[![arxiv logo](/static/browse/0.3.4/images/arxiv-logo-one-color-white.svg)](/) > [cs](/list/cs/recent) > arXiv:2001.04438

[Help](https://info.arxiv.org/help) | [Advanced Search](https://arxiv.org/search/advanced)

All fields
Title
Author
Abstract
Comments
Journal reference
ACM classification
MSC classification
Report number
arXiv identifier
DOI
ORCID
arXiv author ID
Help pages
Full text

Search

[![arXiv logo](/static/browse/0.3.4/images/arxiv-logomark-small-white.svg)](https://arxiv.org/)

[![Cornell University Logo](/static/browse/0.3.4/images/icons/cu/cornell-reduced-white-SMALL.svg)](https://www.cornell.edu/)

open search

GO

open navigation menu

quick links
-----------

* [Login](https://arxiv.org/login)
* [Help Pages](https://info.arxiv.org/help)
* [About](https://info.arxiv.org/about)



Computer Science > Performance
==============================

**arXiv:2001.04438** (cs)

[Submitted on 13 Jan 2020]

Title:The Two-Pass Softmax Algorithm
====================================

Authors:[Marat Dukhan](https://arxiv.org/search/cs?searchtype=author&query=Dukhan,+M), [Artsiom Ablavatski](https://arxiv.org/search/cs?searchtype=author&query=Ablavatski,+A)

View a PDF of the paper titled The Two-Pass Softmax Algorithm, by Marat Dukhan and Artsiom Ablavatski

[View PDF](/pdf/2001.04438)
> Abstract:The softmax (also called softargmax) function is widely used in machine learning models to normalize real-valued scores into a probability distribution. To avoid floating-point overflow, the softmax function is conventionally implemented in three passes: the first pass to compute the normalization constant, and two other passes to compute outputs from normalized inputs. We analyze two variants of the Three-Pass algorithm and demonstrate that in a well-optimized implementation on HPC-class processors performance of all three passes is limited by memory bandwidth. We then present a novel algorithm for softmax computation in just two passes. The proposed Two-Pass algorithm avoids both numerical overflow and the extra normalization pass by employing an exotic representation for intermediate values, where each value is represented as a pair of floating-point numbers: one representing the "mantissa" and another representing the "exponent". Performance evaluation demonstrates that on out-of-cache inputs on an Intel Skylake-X processor the new Two-Pass algorithm outperforms the traditional Three-Pass algorithm by up to 28% in AVX512 implementation, and by up to 18% in AVX2 implementation. The proposed Two-Pass algorithm also outperforms the traditional Three-Pass algorithm on Intel Broadwell and AMD Zen 2 processors. To foster reproducibility, we released an open-source implementation of the new Two-Pass Softmax algorithm and other experiments in this paper as a part of XNNPACK library at [this http URL](http://GitHub.com/google/XNNPACK).

|  |  |
| --- | --- |
| Subjects: | Performance (cs.PF); Machine Learning (cs.LG) |
| Cite as: | [arXiv:2001.04438](https://arxiv.org/abs/2001.04438) [cs.PF] |
|  | (or  [arXiv:2001.04438v1](https://arxiv.org/abs/2001.04438v1) [cs.PF] for this version) |
|  | <https://doi.org/10.48550/arXiv.2001.04438> Focus to learn more  arXiv-issued DOI via DataCite |

Submission history
------------------

From: Marat Dukhan [[view email](/show-email/2c08da59/2001.04438)]   
 **[v1]**
Mon, 13 Jan 2020 18:17:57 UTC (134 KB)

Full-text links:

Access Paper:
-------------

View a PDF of the paper titled The Two-Pass Softmax Algorithm, by Marat Dukhan and Artsiom Ablavatski

* [View PDF](/pdf/2001.04438)
* [TeX Source](/src/2001.04438)

[view license](http://arxiv.org/licenses/nonexclusive-distrib/1.0/ "Rights to this article")

Current browse context:

cs.PF

[< prev](/prevnext?id=2001.04438&function=prev&context=cs.PF "previous in cs.PF (accesskey p)")
  |   
[next >](/prevnext?id=2001.04438&function=next&context=cs.PF "next in cs.PF (accesskey n)")

[new](/list/cs.PF/new)
 | 
[recent](/list/cs.PF/recent)
 | [2020-01](/list/cs.PF/2020-01)

Change to browse by:

[cs](/abs/2001.04438?context=cs)  
[cs.LG](/abs/2001.04438?context=cs.LG)

### References & Citations

* [NASA ADS](https://ui.adsabs.harvard.edu/abs/arXiv:2001.04438)
* [Google Scholar](https://scholar.google.com/scholar_lookup?arxiv_id=2001.04438)
* [Semantic Scholar](https://api.semanticscholar.org/arXiv:2001.04438)

### [DBLP](https://dblp.uni-trier.de) - CS Bibliography

[listing](https://dblp.uni-trier.de/db/journals/corr/corr2001.html#abs-2001-04438 "listing on DBLP") | [bibtex](https://dblp.uni-trier.de/rec/bibtex/journals/corr/abs-2001-04438 "DBLP bibtex record")

[Marat Dukhan](https://dblp.uni-trier.de/search/author?author=Marat%20Dukhan "DBLP author search")

export BibTeX citation
Loading...

BibTeX formatted citation
-------------------------

×

loading...

Data provided by:

### Bookmark

[![BibSonomy logo](/static/browse/0.3.4/images/icons/social/bibsonomy.png)](http://www.bibsonomy.org/BibtexHandler?requTask=upload&url=https://arxiv.org/abs/2001.04438&description=The Two-Pass Softmax Algorithm "Bookmark on BibSonomy")
[![Reddit logo](/static/browse/0.3.4/images/icons/social/reddit.png)](https://reddit.com/submit?url=https://arxiv.org/abs/2001.04438&title=The Two-Pass Softmax Algorithm "Bookmark on Reddit")



Bibliographic Tools

Bibliographic and Citation Tools
================================

Bibliographic Explorer Toggle

Bibliographic Explorer *([What is the Explorer?](https://info.arxiv.org/labs/showcase.html#arxiv-bibliographic-explorer))*

Connected Papers Toggle

Connected Papers *([What is Connected Papers?](https://www.connectedpapers.com/about))*

Litmaps Toggle

Litmaps *([What is Litmaps?](https://www.litmaps.co/))*

scite.ai Toggle

scite Smart Citations *([What are Smart Citations?](https://www.scite.ai/))*

Code, Data, Media

Code, Data and Media Associated with this Article
=================================================

alphaXiv Toggle

alphaXiv *([What is alphaXiv?](https://alphaxiv.org/))*

Links to Code Toggle

CatalyzeX Code Finder for Papers *([What is CatalyzeX?](https://www.catalyzex.com))*

DagsHub Toggle

DagsHub *([What is DagsHub?](https://dagshub.com/))*

GotitPub Toggle

Gotit.pub *([What is GotitPub?](http://gotit.pub/faq))*

Huggingface Toggle

Hugging Face *([What is Huggingface?](https://huggingface.co/huggingface))*

Links to Code Toggle

Papers with Code *([What is Papers with Code?](https://paperswithcode.com/))*

ScienceCast Toggle

ScienceCast *([What is ScienceCast?](https://sciencecast.org/welcome))*

Demos

Demos
=====

Replicate Toggle

Replicate *([What is Replicate?](https://replicate.com/docs/arxiv/about))*

Spaces Toggle

Hugging Face Spaces *([What is Spaces?](https://huggingface.co/docs/hub/spaces))*

Spaces Toggle

TXYZ.AI *([What is TXYZ.AI?](https://txyz.ai))*

Related Papers

Recommenders and Search Tools
=============================

Link to Influence Flower

Influence Flower *([What are Influence Flowers?](https://influencemap.cmlab.dev/))*

Core recommender toggle

CORE Recommender *([What is CORE?](https://core.ac.uk/services/recommender))*

* Author
* Venue
* Institution
* Topic


About arXivLabs

arXivLabs: experimental projects with community collaborators
=============================================================

arXivLabs is a framework that allows collaborators to develop and share new arXiv features directly on our website.

Both individuals and organizations that work with arXivLabs have embraced and accepted our values of openness, community, excellence, and user data privacy. arXiv is committed to these values and only works with partners that adhere to them.

Have an idea for a project that will add value for arXiv's community? [**Learn more about arXivLabs**](https://info.arxiv.org/labs/index.html).

[Which authors of this paper are endorsers?](/auth/show-endorsers/2001.04438) |
[Disable MathJax](javascript:setMathjaxCookie()) ([What is MathJax?](https://info.arxiv.org/help/mathjax.html))



* [About](https://info.arxiv.org/about)
* [Help](https://info.arxiv.org/help)

* contact arXivClick here to contact arXiv
   [Contact](https://info.arxiv.org/help/contact.html)
* subscribe to arXiv mailingsClick here to subscribe
   [Subscribe](https://info.arxiv.org/help/subscribe)



* [Copyright](https://info.arxiv.org/help/license/index.html)
* [Privacy Policy](https://info.arxiv.org/help/policies/privacy_policy.html)

* [Web Accessibility Assistance](https://info.arxiv.org/help/web_accessibility.html)
* [arXiv Operational Status](https://status.arxiv.org)